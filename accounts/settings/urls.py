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

from django.conf.urls import url
from . import views


urlpatterns = (
    url(r'^$', views.HomeView.as_view(), name='home'),
    url(r'^api-access/reset-password$', views.ResetApiPasswordView.as_view(), name='reset_api_password'),
    url(r'^api-access$', views.ApiAccessView.as_view(), name='api_access'),
    url(r'^change-password$', views.ChangePasswordView.as_view(), name='change_password'),
    url(r'^delete-account$', views.DeleteAccountView.as_view(), name='delete_account'),
    url(r'^journal/clear$', views.ClearJournalView.as_view(), name='clear_journal'),
    url(r'^journal$', views.JournalView.as_view(), name='journal'),
    url(r'^timezone$', views.TimezoneView.as_view(), name='timezone'),
)