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

from django.core.exceptions import ValidationError
from ydns import forms
from .enum import DomainAccessType
from .utils import validate_domain_name, DomainValidationResult


class CreateForm(forms.HorizontalForm):
    name = forms.CharField(placeholder='example.xyz',
                           label='Domain name')
    access_type = forms.ChoiceField(label='Access Type')
    public_owner = forms.BooleanField(label='Publish owner details for this domain', required=False)

    field_css = 'col-lg-9 col-md-9'

    def __init__(self, access_type_choices, **kwargs):
        super(CreateForm, self).__init__(**kwargs)
        self.fields['access_type'].choices = access_type_choices

    def clean_access_type(self):
        return DomainAccessType(self.cleaned_data['access_type'])

    def clean_name(self):
        result, servers, message = validate_domain_name(self.cleaned_data['name'])

        if result != DomainValidationResult.OK:
            raise ValidationError(str(result))

        return self.cleaned_data['name'].encode('idna').decode('ascii').lower()