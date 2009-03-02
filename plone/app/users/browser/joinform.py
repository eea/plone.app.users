#!/usr/bin/env python
# encoding: utf-8
"""
joinform.py
"""


from zope.interface import Interface
from zope.component import getUtility

from zope import schema
from zope.formlib import form
from zope.app.form.browser import TextWidget, CheckBoxWidget

from plone.app.controlpanel import PloneMessageFactory as _

from Products.CMFCore.interfaces import ISiteRoot
from Products.CMFCore.utils import getToolByName

from Products.Five.formlib.formbase import PageForm
from ZODB.POSException import ConflictError

from Products.statusmessages.interfaces import IStatusMessage

from userdata import IUserDataSchema


# Define constants from the Join schema that should be added to the
# vocab of the join fields setting in usergroupssettings controlpanel.
JOIN_CONST = ['username', 'password', 'mail_me']

class IJoinSchema(Interface):

    username = schema.ASCIILine(title=_(u'label_user_name', default=u'User Name'),
                               description=_(u'help_user_name_creation_casesensitive',
                               default=u"Enter a user name, usually something "
                               "like 'jsmith'. "
                               "No spaces or special characters. "
                               "Usernames and passwords are case sensitive, "
                               "make sure the caps lock key is not enabled. "
                               "This is the name used to log in."))

    password = schema.Password(title=_(u'label_password', default=u'Password'),
                               description=_(u'help_password_creation',
                                             default=u'Minimum 5 characters.'))

    password_ctl = schema.Password(title=_(u'label_confirm_password',
                                    default=u'Confirm password'),
                               description=_(u'help_confirm_password',
                                    default=u"Re-enter the password. "
                                    "Make sure the passwords are identical."))

    mail_me = schema.Bool(title=_(u'label_mail_password',
                                    default=u"Send a mail with the password"),
                          default=False)

def FullNameWidget(field, request):

    """ Change the description of the widget """
    
    field.description = _(u'help_full_name_creation',
                            default=u"Enter full name, eg. John Smith.")
    widget = TextWidget(field, request)
    return widget

def EmailWidget(field, request):

    """ Change the description of the widget """
    
    field.description = _(u'help_email_creation',
                    default = u"Enter an email address. "
                    "This is necessary in case the password is lost. "
                    "We respect your privacy, and will not give the address "
                    "away to any third parties or expose it anywhere.")
    widget = TextWidget(field, request)
    return widget

class NoCheckBoxWidget(CheckBoxWidget):
    """ A widget used for _not_ displaying the checkbox.
    """

    def __call__(self):
        """Render the widget to HTML."""
        return ""

def CantChoosePasswordWidget(field, request):

    """ Change the mail_me field widget so it doesn't display the checkbox """

    field.title = u''
    field.readonly = True
    field.description = _(u'label_password_change_mail',
                    default=u"A URL will be generated and e-mailed to you; "
                    "follow the link to reach a page where you can change your "
                    "password and complete the registration process.")
    widget = NoCheckBoxWidget(field, request)
    return widget

class JoinForm(PageForm):

    """ Dynamically get fields from user data, through admin
        config settings.
    """
    
    label = _(u'heading_registration_form', default=u'Registration Form')
    description = _(u"")
    form_name = _(u'legend_personal_details', default=u'Personal Details')

    @property
    def form_fields(self):

        """ form_fields is dynamic in this form, to be able to handle
        different join styles.
        """

        portal = getUtility(ISiteRoot)
        props = getToolByName(self.context, 'portal_properties').site_properties
        join_fields = list(props.getProperty('join_form_fields'))

        canSetOwnPassword = not portal.getProperty('validate_email', True)
        

        # Check on required join fields
        #
        if not 'username' in join_fields:

            join_fields.insert(0, 'username')

        if canSetOwnPassword:
            # Add password if needed
            #
            if not 'password' in join_fields:
                
                join_fields.insert(join_fields.index('username') + 1,
                                   'password')

            # Add password_ctl after password
            #
            if not 'password_ctl' in join_fields:
                
                join_fields.insert(join_fields.index('password') + 1,
                                   'password_ctl')

            # Add email_me after password_ctl
            #
            if not 'mail_me' in join_fields:
                
                join_fields.insert(join_fields.index('password_ctl') + 1,
                                   'mail_me')

        # Can the user actually set his/her own password? If not, skip
        # password fields in final list.
        #
        if not canSetOwnPassword:
            if 'password' in join_fields:
                del join_fields[join_fields.index('password')]
            if 'password_ctl' in join_fields:
                del join_fields[join_fields.index('password_ctl')]

        # We need fields from both schemata here.
        #
        all_fields = form.Fields(IUserDataSchema) + form.Fields(IJoinSchema)
        all_fields['fullname'].custom_widget = FullNameWidget
        all_fields['email'].custom_widget = EmailWidget
        if portal.validate_email:
            all_fields['mail_me'].custom_widget = CantChoosePasswordWidget


        # Pass the list of join form fields as a reference to the
        # Fields constructor, and return.
        #
        return form.Fields(*[all_fields[id] for id in join_fields])


    @form.action(_(u'label_register', default=u'Register'), name=u'register')
    def action_join(self, action, data):
        
        portal = getUtility(ISiteRoot)
        registration = portal.portal_registration

        username = data['username']

        password = data.get('password') or registration.generatePassword()

        try:
            registration.addMember(username, password, properties=data, REQUEST=self.request)
        except AttributeError, ValueError:

            failMessage = _(u'The login name you selected is already in use or is not valid. Please choose another.')

            IStatusMessage(self.request).addStatusMessage(_(failMessage),
                                                          type="error")
            return

        if portal.validate_email or data.get('mail_me', 0):
            try:
                registration.registeredNotify(username)
            except ConflictError:
                IStatusMessage(self.request).addStatusMessage(_("Conflict error"),
                                                          type="error")
                return
            except Exception:
                IStatusMessage(self.request).addStatusMessage(_("Couldn't send mail"),
                                                          type="error")
                return

            self.context.acl_users.userFolderDelUsers([username,], REQUEST=self.request)
            self.status = (_(u'status_fatal_password_mail',
                    default=u'Failed to create your account: we were unable to send your password to your email address: ${address}',
                    mapping={u'address' : data.get('email', '')}))
        else:
            self.status = (_(u'status_nonfatal_password_mail',
                    default=u'You account has been created, but we were unable to send your password to your email address: ${address}',
                    mapping={u'address' : data.get('email', '')}))

        self.request.response.redirect('registered')