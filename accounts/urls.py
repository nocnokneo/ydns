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

from django.conf.urls import include, url
from . import signals as _signals  # signal machinery
from . import views

urlpatterns = (
    url(r'^activate/(?P<alias>\S{16})/(?P<token>\S{64})$', views.ActivationView.as_view(), name='activate'),
    url(r'^admin/', include('accounts.admin.urls', namespace='admin')),
    url(r'^logout$', views.LogoutView.as_view(), name='logout'),
    url(r'^oauth/facebook$', views.FacebookSignInView.as_view(), name='facebook_sign_in'),
    url(r'^oauth/github$', views.GithubSignInView.as_view(), name='github_sign_in'),
    url(r'^oauth/google$', views.GoogleSignInView.as_view(), name='google_sign_in'),
    url(r'^reset-password/(?P<alias>\S{16})/(?P<token>\S{64})$', views.SetPasswordView.as_view(), name='set_password'),
    url(r'^reset-password$', views.ResetPasswordView.as_view(), name='reset_password'),
    url(r'^settings/', include('accounts.settings.urls', namespace='settings')),
)
