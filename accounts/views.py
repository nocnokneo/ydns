##
# YDNS Core
#
# Copyright (c) 2015 Christian Jurk <commx@commx.ws>
#
# Permission is hereby granted, free of charge, to any person obtaining a copy
# of this software and associated documentation files (the "Software"), to deal
# in the Software without restriction, including without limitation the rights
# to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
# copies of the Software, and to permit persons to whom the Software is
# furnished to do so, subject to the following conditions:
#
# The above copyright notice and this permission notice shall be included in
# all copies or substantial portions of the Software.
#
# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
# IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
# FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
# AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
# LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
# OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
# SOFTWARE.
##

from accounts.oauth import facebook, github, google
from accounts.models import ActivationRequest, PasswordRequest, User
from dateutil.relativedelta import relativedelta
from django.conf import settings
from django.contrib import messages
from django.contrib.auth import authenticate, login, logout
from django.core.urlresolvers import reverse
from django.shortcuts import get_object_or_404
from django.utils import timezone
from ydns.utils.http import absolute_url
from ydns.utils.mail import EmailMessage
from ydns.views import FormView, TemplateView, View
from . import forms
from .enum import UserType
from .utils import activate_timezone, deactivate_timezone

import json


class _AnonymousView(TemplateView):
    """
    Anonymous base view.
    """
    require_login = False
    require_admin = False


class ActivationView(_AnonymousView):
    """
    Account activation.
    """
    def get_context_data(self, **kwargs):
        context = super(ActivationView, self).get_context_data(**kwargs)
        context['activation_request'] = get_object_or_404(ActivationRequest,
                                                          user__alias=self.kwargs['alias'],
                                                          token=self.kwargs['token'],
                                                          date_created__gte=timezone.now() - relativedelta(hours=24))
        return context

    def get(self, request, *args, **kwargs):
        context = self.get_context_data(**kwargs)
        activation_request = context.pop('activation_request')

        # Activate user account
        activation_request.user.is_active = True
        activation_request.user.save()
        activation_request.user.add_to_log('Activation')

        # Delete activation request object
        activation_request.delete()

        messages.success(request, 'Your account has been activated successfully.')
        return self.redirect('login')


class FacebookSignInView(View):
    """
    OAuth2 based login via Facebook Connect.

    For this, we use the "email" scope for accessing
    the email address of the user. It is then used
    to maintain a local user account associated with
    that email address.
    """
    requires_admin = False
    requires_login = False

    URL_GET_TOKEN = 'https://graph.facebook.com/oauth/access_token'
    URL_PROFILE = 'https://graph.facebook.com/me?'

    @staticmethod
    def create_user(email):
        """
        Create a new user account.

        :param email: Email address
        :return:
        """
        user = User.objects.create_user(email,
                                        type=UserType.FACEBOOK,
                                        is_active=True)

        user.add_to_log('Account created via Facebook login')

        # Send welcome Email
        context = {'user': user}
        msg = EmailMessage('Welcome to YDNS',
                           tpl='accounts/welcome_facebook.mail',
                           context=context)
        msg.send(to=[user.email])

        return user

    @staticmethod
    def login(request, user):
        """
        Perform actual login.

        :param request: HttpRequest
        :param user: User
        """
        user.add_to_log('Login via Facebook')
        return LoginView.login(request, user)

    def get(self, request, *args, **kwargs):
        """
        Verify the OAuth2 response from Facebook.

        :param request: HttpRequest
        :param args: tuple
        :param kwargs: dict
        :return: HttpResponse
        """
        if not request.GET.get('state'):
            return self.response_error(request, 'Missing state property.')
        elif not request.GET.get('code'):
            return self.response_error(request, 'Missing code property.')

        state = request.GET['state']
        code = request.GET['code']

        if state != request.session.get('fb_state'):
            return self.response_error(request, 'Invalid state.')

        facebook.redirect_uri = absolute_url(request, 'accounts:facebook_sign_in')
        facebook.scope = ''  # need to reset scope to '', because otherwise we'll get trouble

        try:
            facebook.fetch_token(self.URL_GET_TOKEN,
                                 code=code,
                                 client_secret=settings.FACEBOOK_APP_SECRET)
        except Exception:
            return self.response_error(request, 'An error occurred while verifying response.')

        response = facebook.get(self.URL_PROFILE)

        try:
            data = json.loads(response.content.decode('utf-8'))
        except ValueError:
            return self.response_error(request, 'Invalid response format.')

        email_address = None

        if isinstance(data, dict) and data.get('email'):
            email_address = data['email']

        if not email_address:
            return self.response_error(request, 'No valid account-based email address found.')

        # Now check if the account exists and login
        user = None

        try:
            user = User.objects.get(email__iexact=email_address)
        except User.DoesNotExist:
            user = self.create_user(email_address)

        if not user.is_active:
            return self.response_error(request, 'Your account is inactive.')
        elif user.type != UserType.FACEBOOK:
            return self.response_error(request, 'Account type mismatch.')
        else:
            return self.login(request, user)

    def post(self, request, *args, **kwargs):
        """
        Request a OAuth2 login via Facebook.

        This has to be done through POST to ensure that no
        cross-site requests are happening (CSRF protection).

        :param request: HttpRequest
        :param args: tuple
        :param kwargs: dict
        :return: HttpResponse
        """
        facebook.redirect_uri = absolute_url(request, 'accounts:facebook_sign_in')
        facebook.scope = 'email'

        authorization_url, state = facebook.authorization_url('https://www.facebook.com/dialog/oauth')

        request.session['fb_state'] = state

        return self.redirect(authorization_url)

    @classmethod
    def response_error(cls, request, message):
        messages.error(request, message)
        return cls.redirect('accounts:login')


class GithubSignInView(View):
    """
    OAuth2 based login via GitHub.

    No scope is used; the default is to have read-only
    access to profile details, which is fine for us.
    """
    requires_admin = False
    requires_login = False

    URL_GET_TOKEN = 'https://github.com/login/oauth/access_token'
    URL_USER_PROFILE = 'https://api.github.com/user'

    @staticmethod
    def create_user(email):
        """
        Create a new user account.

        :param email: Email address
        :return:
        """
        user = User.objects.create_user(email,
                                        type=UserType.GITHUB,
                                        is_active=True)

        user.add_to_log('Account created via GitHub login')

        # Send welcome Email
        context = {'user': user}
        msg = EmailMessage('Welcome to YDNS',
                           tpl='accounts/welcome_github.mail',
                           context=context)
        msg.send(to=[user.email])

        return user

    @staticmethod
    def login(request, user):
        """
        Perform actual login.

        :param request: HttpRequest
        :param user: User
        """
        user.add_to_log('Login via GitHub')
        return LoginView.login(request, user)

    def get(self, request, *args, **kwargs):
        """
        Verify the OAuth2 response from GitHub.

        :param request: HttpRequest
        :param args: tuple
        :param kwargs: dict
        :return: HttpResponse
        """
        if not request.GET.get('state'):
            return self.response_error(request, 'Missing state property.')
        elif not request.GET.get('code'):
            return self.response_error(request, 'Missing code property.')

        state = request.GET['state']
        code = request.GET['code']

        if state != request.session.get('github_state'):
            return self.response_error(request, 'Invalid state.')

        github.redirect_uri = absolute_url(request, 'accounts:github_sign_in')
        github.scope = ''  # need to reset scope to '', because otherwise we'll get trouble

        try:
            github.fetch_token(self.URL_GET_TOKEN,
                               code=code,
                               client_secret=settings.GITHUB_CLIENT_SECRET)
        except Exception:
            return self.response_error(request, 'An error occurred while verifying response.')

        response = github.get(self.URL_USER_PROFILE)

        try:
            data = json.loads(response.content.decode('utf-8'))
        except ValueError:
            return self.response_error(request, 'Invalid response format.')

        email_address = None

        if isinstance(data, dict) and data.get('email'):
            email_address = data['email']

        if not email_address:
            return self.response_error(request, 'No valid account-based email address found.')

        # Now check if the account exists and login
        try:
            user = User.objects.get(email__iexact=email_address)
        except User.DoesNotExist:
            user = self.create_user(email_address)

        if not user.is_active:
            return self.response_error(request, 'Your account is inactive.')
        elif user.type != UserType.GITHUB:
            return self.response_error(request, 'Account type mismatch.')
        else:
            return self.login(request, user)

    def post(self, request, *args, **kwargs):
        """
        Request a OAuth2 login via GitHub.

        This has to be done through POST to ensure that no
        cross-site requests are happening (CSRF protection).

        :param request: HttpRequest
        :param args: tuple
        :param kwargs: dict
        :return: HttpResponse
        """
        github.redirect_uri = absolute_url(request, 'accounts:github_sign_in')
        github.scope = None

        authorization_url, state = github.authorization_url('https://github.com/login/oauth/authorize')

        request.session['github_state'] = state

        return self.redirect(authorization_url)

    @classmethod
    def response_error(cls, request, message):
        messages.error(request, message)
        return cls.redirect('accounts:login')


class GoogleSignInView(_AnonymousView):
    """
    OAuth2 based login via Google.

    For this, we use the "email" scope for accessing
    the email address of the user. It is then used
    to maintain a local user account associated with
    that email address.
    """
    URL_GET_TOKEN = 'https://accounts.google.com/o/oauth2/token'
    URL_PLUS_API_PEOPLE_GET = 'https://www.googleapis.com/plus/v1/people/me'

    @staticmethod
    def create_user(email):
        """
        Create a new user account.

        :param email: Email address
        :return:
        """
        user = User.objects.create_user(email,
                                        type=UserType.GOOGLE,
                                        is_active=True)

        user.add_to_log('Account created via Google login')

        # Send welcome Email
        context = {'user': user}
        msg = EmailMessage('Welcome to YDNS',
                           tpl='accounts/welcome_google.mail',
                           context=context)
        msg.send(to=[user.email])

        return user

    @staticmethod
    def login(request, user):
        """
        Perform actual login.

        :param request: HttpRequest
        :param user: User
        """
        user.add_to_log('Login via Google')
        return LoginView.login(request, user)

    def get(self, request, *args, **kwargs):
        """
        Verify the OAuth2 response from Google.

        :param request: HttpRequest
        :param args: tuple
        :param kwargs: dict
        :return: HttpResponse
        """
        if not request.GET.get('state'):
            return self.response_error(request, 'Missing state property.')
        elif not request.GET.get('code'):
            return self.response_error(request, 'Missing code property.')

        state = request.GET['state']
        code = request.GET['code']

        if state != request.session.get('gapi_state'):
            return self.response_error(request, 'Invalid state.')

        google.redirect_uri = absolute_url(request, 'accounts:google_sign_in')
        google.scope = ''  # need to reset scope to '', because otherwise we'll get trouble

        try:
            google.fetch_token(self.URL_GET_TOKEN,
                               code=code,
                               client_secret=settings.GAPI_CLIENT_SECRET)
        except Exception:
            return self.response_error(request, 'An error occurred while verifying response.')

        response = google.get(self.URL_PLUS_API_PEOPLE_GET)

        try:
            data = json.loads(response.content.decode('utf-8'))
        except ValueError:
            return self.response_error(request, 'Invalid response format.')

        email_address = None

        if isinstance(data, dict) and data.get('emails'):
            for i in data['emails']:
                if i['type'] == 'account':
                    email_address = i['value']
                    break

        if not email_address:
            return self.response_error(request, 'No valid account-based email address found.')

        # Now check if the account exists and login
        user = None

        try:
            user = User.objects.get(email__iexact=email_address)
        except User.DoesNotExist:
            user = self.create_user(email_address)

        if not user.is_active:
            return self.response_error(request, 'Your account is inactive.')
        elif user.type != UserType.GOOGLE:
            return self.response_error(request, 'Account type mismatch.')
        else:
            return self.login(request, user)

    def post(self, request, *args, **kwargs):
        """
        Request a OAuth2 login via Google.

        This has to be done through POST to ensure that no
        cross-site requests are happening (CSRF protection).

        :param request: HttpRequest
        :param args: tuple
        :param kwargs: dict
        :return: HttpResponse
        """
        google.redirect_uri = absolute_url(request, 'accounts:google_sign_in')
        google.scope = 'email'

        authorization_url, state = google.authorization_url(
            'https://accounts.google.com/o/oauth2/auth',
            access_type='offline',
            approval_prompt='force')

        request.session['gapi_state'] = state

        return self.redirect(authorization_url)

    @classmethod
    def response_error(cls, request, message):
        messages.error(request, message)
        return cls.redirect('login')


class LoginView(_AnonymousView, FormView):
    form_class = forms.LoginForm
    template_name = 'accounts/login.html'

    @classmethod
    def login(cls, request, user, redirect=None):
        """
        Perform login.

        :param request: HttpRequest
        :param user: User instance
        :param redirect: Redirection url, optional
        :return: HttpResponse
        """
        if not hasattr(user, 'backend'):
            user.backend = settings.AUTHENTICATION_BACKENDS[0]

        login(request, user)

        if user.timezone:
            activate_timezone(request)

        return cls.redirect(redirect or 'dashboard')

    def get_context_data(self, **kwargs):
        context = super(LoginView, self).get_context_data(**kwargs)
        context['next'] = self.request.GET.get('next', self.request.POST.get('next'))
        return context

    def form_valid(self, form):
        context = self.get_context_data(**self.kwargs)
        user = authenticate(email=form.cleaned_data['email'],
                            password=form.cleaned_data['password'])

        if user is not None:
            if not user.is_active:
                form.add_error('email', 'Account is disabled')
        else:
            form.add_error('email', 'Invalid Email and/or password')

        if not form.is_valid():
            return self.form_invalid(form)

        return self.login(self.request, user, context['next'])


class LogoutView(_AnonymousView):
    """
    Perform account logout.
    """
    def dispatch(self, request, *args, **kwargs):
        if request.user.is_authenticated():
            logout(request)
            deactivate_timezone(request)
            messages.info(request, 'You have been logged out.')
        return self.redirect('home')


class ResetPasswordView(_AnonymousView, FormView):
    """
    Reset password view.
    """
    form_class = forms.ResetPasswordForm
    template_name = 'accounts/reset_password.html'

    @classmethod
    def create_token(cls, request, user):
        """
        Create password reset request.

        :param request: HttpRequest
        :param user: User
        :return: HttpResponse
        """
        token = User.objects.make_random_password(64)
        rp = PasswordRequest.objects.create(user=user, token=token)
        user.add_to_log('Password reset request')

        # Send email
        url = absolute_url(request, 'accounts:set_password', args=(user.alias, token))
        context = {'user': user, 'token': token, 'url': url}
        msg = EmailMessage('Password reset',
                           tpl='accounts/reset_password.mail',
                           context=context)
        msg.send(to=[user.email])

        messages.success(request, 'Instructions on how to reset your password has been sent via email. '
                                  'Please check your mail box in a few moments.')

        return cls.redirect('login')

    def form_valid(self, form):
        """
        Validate form and processing of it.

        :param form: Bound form
        :return: HttpResponse
        """
        try:
            user = User.objects.get(email__iexact=form.cleaned_data['email'])
        except User.DoesNotExist:
            form.add_error('email', 'This email address is not known to us')
        else:
            delta = timezone.now() - relativedelta(hours=24)
            qs = PasswordRequest.objects.filter(user=user, date_created__gte=delta)

            if qs.count() > 0:
                form.add_error('email', 'You have already requested a password reset within the last 24 hours.')
            else:
                return self.create_token(self.request, user)

        return self.form_invalid(form)


class SetPasswordView(_AnonymousView, FormView):
    """
    Set a new password based on a password reset request.
    """
    form_class = forms.SetPasswordForm
    template_name = 'accounts/set_password.html'

    def form_valid(self, form):
        context = self.get_context_data(**self.kwargs)
        password_request = context.pop('password_request')

        if form.cleaned_data['new'] != form.cleaned_data['repeat']:
            for k in ('new', 'repeat'):
                form.add_error(k, 'The passwords do not match.')

        if not form.is_valid():
            return self.form_invalid(form)

        user = password_request.user
        user.set_password(form.cleaned_data['new'])
        user.save()
        user.add_to_log('Password changed')

        password_request.delete()
        messages.info(self.request, 'Your password has been changed.')

        return self.redirect('login')

    def get_context_data(self, **kwargs):
        context = super(SetPasswordView, self).get_context_data(**kwargs)

        delta = timezone.now() - relativedelta(hours=24)
        context['password_request'] = get_object_or_404(PasswordRequest,
                                                        user__alias=self.kwargs['alias'],
                                                        token=self.kwargs['token'],
                                                        date_created__gte=delta)
        return context


class SignupView(_AnonymousView, FormView):
    """
    New user registration.
    """
    form_class = forms.SignupForm
    template_name = 'accounts/signup.html'

    def create_user(self, email, password):
        """
        Create user account.

        :param email: Email address
        :param password: Password
        :return: HttpResponse
        """
        user = User.objects.create_user(email, password)
        user.add_to_log('User account created')

        # Create activation request
        token = User.objects.make_random_password(64)
        ActivationRequest.objects.create(user=user, token=token)

        # Send email
        url = absolute_url(self.request, 'accounts:activate', args=(user.alias, token))
        context = {'user': user, 'token': token, 'url': url}
        msg = EmailMessage('Welcome to YDNS',
                           tpl='accounts/welcome.mail',
                           context=context)
        msg.send(to=[user.email])

        messages.success(self.request, 'We have sent activation instructions to your email address. '
                                       'Please check your mail box in a few moments.')
        return self.redirect('login')

    def form_valid(self, form):
        """
        Additional form validation and processing.

        :param form: Bound form
        :return: HttpResponse
        """
        if form.cleaned_data['password'] != form.cleaned_data['repeat']:
            for k in ('password', 'repeat'):
                form.add_error(k, 'The passwords do not match.')
            return self.form_invalid(form)

        try:
            User.objects.get(email__iexact=form.cleaned_data['email'])
        except User.DoesNotExist:
            pass
        else:
            form.add_error('email', 'This email address is already in use')

        if not form.is_valid():
            return self.form_invalid(form)

        return self.create_user(form.cleaned_data['email'], form.cleaned_data['password'])

    def get_form_kwargs(self):
        kwargs = super(SignupView, self).get_form_kwargs()
        kwargs['terms_url'] = reverse('terms')
        return kwargs