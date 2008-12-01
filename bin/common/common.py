# -*- encoding: utf-8 -*-
##############################################################################
#
#    OpenERP, Open Source Management Solution	
#    Copyright (C) 2004-2008 Tiny SPRL (<http://tiny.be>). All Rights Reserved
#    $Id$
#
#    This program is free software: you can redistribute it and/or modify
#    it under the terms of the GNU General Public License as published by
#    the Free Software Foundation, either version 3 of the License, or
#    (at your option) any later version.
#
#    This program is distributed in the hope that it will be useful,
#    but WITHOUT ANY WARRANTY; without even the implied warranty of
#    MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#    GNU General Public License for more details.
#
#    You should have received a copy of the GNU General Public License
#    along with this program.  If not, see <http://www.gnu.org/licenses/>.
#
##############################################################################

import gtk
from gtk import glade
import gobject

import gettext

import os
import sys
import common
import logging
from options import options
import service

import ConfigParser

import threading
import time

import rpc

#
# Upgrade this number to force the client to ask the survey
#
SURVEY_VERSION = '3'

def _search_file(file, dir='path.share'):
    tests = [
        lambda x: os.path.join(os.getcwd(), os.path.dirname(sys.argv[0]), x),
        lambda x: os.path.join(os.getcwd(), os.path.dirname(sys.argv[0]), 'pixmaps', x),
        lambda x: os.path.join(options.options[dir],x),
    ]
    for func in tests:
        x = func(file)
        if os.path.exists(x):
            return x
    return False

terp_path = _search_file
terp_path_pixmaps = lambda x: _search_file(x, 'path.pixmaps')

OPENERP_ICON = gtk.gdk.pixbuf_new_from_file(
            terp_path_pixmaps('openerp-icon.png'))

def selection(title, values, alwaysask=False, parent=None):
    if not values or len(values)==0:
        return None
    elif len(values)==1 and (not alwaysask):
        key = values.keys()[0]
        return (key, values[key])

    xml = glade.XML(terp_path("openerp.glade"), "win_selection", gettext.textdomain())
    win = xml.get_widget('win_selection')
    if not parent:
        parent = service.LocalService('gui.main').window
    win.set_icon(OPENERP_ICON)
    win.set_transient_for(parent)

    label = xml.get_widget('win_sel_title')
    if title:
        label.set_text(title)

    list = xml.get_widget('win_sel_tree')
    list.get_selection().set_mode('single')
    cell = gtk.CellRendererText()
    column = gtk.TreeViewColumn("Widget", cell, text=0)
    list.append_column(column)
    list.set_search_column(0)
    model = gtk.ListStore(gobject.TYPE_STRING)
    keys = values.keys()
    keys.sort()
    for val in keys:
        model.append([val])

    list.set_model(model)
    list.connect('row-activated', lambda x,y,z: win.response(gtk.RESPONSE_OK) or True)

    ok = False
    while not ok:
        response = win.run()
        ok = True
        res = None
        if response == gtk.RESPONSE_OK:
            sel = list.get_selection().get_selected()
            if sel:
                (model, iter) = sel
                if iter:
                    res = model.get_value(iter, 0)
                    res = (res, values[res])
                else:
                    ok = False
            else:
                ok = False
        else:
            res = None
    parent.present()
    win.destroy()
    return res

class upload_data_thread(threading.Thread):
    def __init__(self, email, data, type, supportid):
        self.args = [('email',email),('type',type),('supportid',supportid),('data',data)]
        super(upload_data_thread,self).__init__()
    def run(self):
        try:
            import urllib
            args = urllib.urlencode(self.args)
            fp = urllib.urlopen('http://www.openerp.com/scripts/survey.php', args)
            fp.read()
            fp.close()
        except:
            pass

def upload_data(email, data, type='SURVEY', supportid=''):
    a = upload_data_thread(email, data, type, supportid)
    a.start()
    return True

def terp_survey():
    if options.options['survey.position']==SURVEY_VERSION:
        return False
    import pickle
    widnames = ('country','role','industry','employee','hear','system','opensource')
    winglade = glade.XML(common.terp_path("openerp.glade"), "dia_survey", gettext.textdomain())
    win = winglade.get_widget('dia_survey')
    parent = service.LocalService('gui.main').window
    win.set_transient_for(parent)
    win.set_icon(OPENERP_ICON)
    for widname in widnames:
        wid = winglade.get_widget('combo_'+widname)
        wid.child.set_text('(choose one)')
        wid.child.set_editable(False)
    res = win.run()
    if res==gtk.RESPONSE_OK:
        email =  winglade.get_widget('entry_email').get_text()
        company =  winglade.get_widget('entry_company').get_text()
        phone = winglade.get_widget('entry_phone').get_text()
        name = winglade.get_widget('entry_name').get_text()
        result = "\ncompany: "+str(company)
        result += "\nname: " + str(name)
        result += "\nphone: " + str(phone)
        for widname in widnames:
            wid = winglade.get_widget('combo_'+widname)
            result += "\n"+widname+": "+wid.child.get_text()
        result += "\nplan_use: "+str(winglade.get_widget('check_use').get_active())
        result += "\nplan_sell: "+str(winglade.get_widget('check_sell').get_active())
        result += "\nwant_demo: " + str(winglade.get_widget('check_button_demo').get_active())

        buffer = winglade.get_widget('textview_comment').get_buffer()
        iter_start = buffer.get_start_iter()
        iter_end = buffer.get_end_iter()
        result += "\nnote: "+buffer.get_text(iter_start,iter_end,False)
        parent.present()
        win.destroy()
        upload_data(email, result, type='SURVEY '+str(SURVEY_VERSION))
        options.options['survey.position']=SURVEY_VERSION
        options.save()
        common.message(_('Thank you for the feedback !\n\
Your comments have been sent to OpenERP.\n\
You should now start by creating a new database or\n\
connecting to an existing server through the "File" menu.'))
    else:
        parent.present()
        win.destroy()
        common.message(_('Thank you for testing OpenERP !\n\
You should now start by creating a new database or\n\
connecting to an existing server through the "File" menu.'))
    return True


def file_selection(title, filename='', parent=None,
        action=gtk.FILE_CHOOSER_ACTION_OPEN, preview=True, multi=False, filters=None):
    if action == gtk.FILE_CHOOSER_ACTION_OPEN:
        buttons=(gtk.STOCK_CANCEL, gtk.RESPONSE_CANCEL,
            gtk.STOCK_OPEN,gtk.RESPONSE_OK)
    else:
        buttons=(gtk.STOCK_CANCEL, gtk.RESPONSE_CANCEL,
            gtk.STOCK_SAVE, gtk.RESPONSE_OK)
    win = gtk.FileChooserDialog(title, None, action, buttons)
    if not parent:
        parent = service.LocalService('gui.main').window
    win.set_transient_for(parent)
    win.set_icon(OPENERP_ICON)
    win.set_current_folder(options.options['client.default_path'])
    win.set_select_multiple(multi)
    win.set_default_response(gtk.RESPONSE_OK)
    if filters is not None:
        for filter in filters:
            win.add_filter(filter)
    if filename:
        win.set_current_name(filename)

    def update_preview_cb(win, img):
        filename = win.get_preview_filename()
        try:
            pixbuf = gtk.gdk.pixbuf_new_from_file_at_size(filename, 128, 128)
            img.set_from_pixbuf(pixbuf)
            have_preview = True
        except:
            have_preview = False
        win.set_preview_widget_active(have_preview)
        return

    if preview:
        img_preview = gtk.Image()
        win.set_preview_widget(img_preview)
        win.connect('update-preview', update_preview_cb, img_preview)

    button = win.run()
    if button!=gtk.RESPONSE_OK:
        win.destroy()
        return False
    if not multi:
        filepath = win.get_filename()
        if filepath:
            filepath = filepath.decode('utf-8')
            try:
                options.options['client.default_path'] = os.path.dirname(filepath)
            except:
                pass
        parent.present()
        win.destroy()
        return filepath
    else:
        filenames = win.get_filenames()
        if filenames:
            filenames = [x.decode('utf-8') for x in filenames]
            try:
                options.options['client.default_path'] = os.path.dirname(filenames[0])
            except:
                pass
        parent.present()
        win.destroy()
        return filenames

def support(*args):
    import pickle
    wid_list = ['email_entry','id_entry','name_entry','phone_entry','company_entry','error_details','explanation_textview','remark_textview']
    required_wid = ['email_entry', 'name_entry', 'company_name', 'id_entry']
    support_id = options['support.support_id']
    recipient = options['support.recipient']

    sur = glade.XML(terp_path("openerp.glade"), "dia_support",gettext.textdomain())
    win = sur.get_widget('dia_support')
    parent = service.LocalService('gui.main').window
    win.set_transient_for(parent)
    win.set_icon(OPENERP_ICON)
    win.show_all()
    sur.get_widget('id_entry1').set_text(support_id)

    response = win.run()
    if response == gtk.RESPONSE_OK:
        fromaddr = sur.get_widget('email_entry1').get_text()
        id_contract = sur.get_widget('id_entry1').get_text()
        name =  sur.get_widget('name_entry1').get_text()
        phone =  sur.get_widget('phone_entry1').get_text()
        company =  sur.get_widget('company_entry1').get_text()

        urgency = sur.get_widget('urgency_combo1').get_active_text()

        buffer = sur.get_widget('explanation_textview1').get_buffer()
        explanation = buffer.get_text(buffer.get_start_iter(), buffer.get_end_iter())

        buffer = sur.get_widget('remark_textview').get_buffer()
        remarks = buffer.get_text(buffer.get_start_iter(), buffer.get_end_iter())

        content = name +"(%s, %s, %s)"%(id_contract, company, phone) +" has reported the following bug:\n"+ explanation + "\nremarks:\n" + remarks

        if upload_data(fromaddr, content, 'support', id_contract):
            common.message(_('Support request sent !'))

    parent.present()
    win.destroy()
    return True

def error(title, message, details='', parent=None):
    """
    Show an error dialog with the support request or the maintenance
    """
    log = logging.getLogger('common.message')
    log.error('Message %s: %s' % (str(message),details))

    support_id = options['support.support_id']
    recipient = options['support.recipient']
    ids = rpc.session.rpc_exec_auth('/object', 'execute', 'maintenance.contract', 'search',[])
    result = { 'status' : 'ko' }
    if ids:
        result = rpc.session.rpc_exec_auth('/object', 'execute', 'maintenance.contract', '_test_maintenance', ids, {})
    if result['status']=='ko':
        maintenance_contract_message=_('''Maintenance Contract
-----------------------------------------------------------
You have no valid maintenance contract! If you are using
Open ERP, it is highly suggested to take maintenance contract.
The maintenance program offers you:
* Migrations on new versions,
* Bugfix guarantee,
* Monthly announces of bugs,
* Security alerts,
* Access to the customer portal.
* Check the maintenance contract (www.openerp.com)''')
    elif result['status']=='partial':
        maintenance_contract_message=_('''Maintenance Contract
-----------------------------------------------------------
You have a maintenance contract, But you installed modules those
are not covered by your maintenance contract: 
%s
It means we can not offer you the garantee of maintenance on
your whole installation.
The maintenance program includes:
* Migrations on new versions,
* Bugfix guarantee,
* Monthly announces of bugs,
* Security alerts,
* Access to the customer portal.

To include these modules in your maintenance contract, you should
extend your contract with the editor. We will review and validate
your installed modules.

* Extend your maintenance to the modules you used.
* Check your maintenance contract''') % ( ",".join(result['modules']) )

    xmlGlade = glade.XML(terp_path('win_error.glade'), 'dialog_error', gettext.textdomain())
    win = xmlGlade.get_widget('dialog_error')
    if not parent:
        parent=service.LocalService('gui.main').window
    win.set_transient_for(parent)
    win.set_icon(OPENERP_ICON)
    win.set_title("OpenERP - %s" % title)

    xmlGlade.get_widget('title_error').set_markup("<i>%s</i>" % message)

    details_buffer = gtk.TextBuffer()
    details_buffer.set_text(unicode(details,'latin1').encode('utf-8'))
    xmlGlade.get_widget('details_explanation').set_buffer(details_buffer)

    is_ok = result['status'] == 'ok'

    #xmlGlade.get_widget('button_send').set_sensitive(is_ok)
    if not is_ok:
        maintenance_buffer = gtk.TextBuffer()
        maintenance_buffer.set_text(maintenance_contract_message) 
        xmlGlade.get_widget('maintenance_explanation').set_buffer(maintenance_buffer)

    xmlGlade.get_widget('notebook').remove_page(int(not is_ok))

    def send(widget):
        def get_text_from_text_view(textView):
            """Retrieve the buffer from a text view and return the content of this buffer"""
            buffer = textView.get_buffer()
            return buffer.get_text(buffer.get_start_iter(), buffer.get_end_iter())
            

        # Use details_buffer
        id_contract = 0
        traceback = details_buffer
        explanation = get_text_from_text_view(xmlGlade.get_widget('explanation_textview'))
        remarks = get_text_from_text_view(xmlGlade.get_widget('remarks_textview'))

        content = "(%s) has reported the following bug:\n%s\nremarks: %s\nThe traceback is:\n%s" % (
            id_contract, explanation, remarks, traceback
        )

        if upload_data('', content, 'error', id_contract):
            common.message(_('Support request sent !'))
        return

    if is_ok:
        #xmlGlade.signal_connect('on_button_send_clicked', send)
        xmlGlade.signal_connect('on_closebutton_clicked', lambda x : win.destroy())

    response = win.run()
    parent.present()
    win.destroy()
    return True

def message(msg, type=gtk.MESSAGE_INFO, parent=None):
    if not parent:
        parent=service.LocalService('gui.main').window
    dialog = gtk.MessageDialog(parent,
      gtk.DIALOG_MODAL | gtk.DIALOG_DESTROY_WITH_PARENT,
      type, gtk.BUTTONS_OK,
      msg)
    dialog.set_icon(OPENERP_ICON)
    dialog.run()
    parent.present()
    dialog.destroy()
    return True

def to_xml(s):
    return s.replace('&','&amp;').replace('<','&lt;').replace('>','&gt;')

def message_box(title, msg, parent=None):
    dia = glade.XML(terp_path("openerp.glade"), "dia_message_box",gettext.textdomain())
    win = dia.get_widget('dia_message_box')
    l = dia.get_widget('msg_title')
    l.set_text(title)

    buffer = dia.get_widget('msg_tv').get_buffer()
    iter_start = buffer.get_start_iter()
    buffer.insert(iter_start, msg)

    if not parent:
        parent=service.LocalService('gui.main').window
    win.set_transient_for(parent)
    win.set_icon(OPENERP_ICON)

    response = win.run()
    parent.present()
    win.destroy()
    return True


def warning(msg, title='', parent=None):
    if not parent:
        parent=service.LocalService('gui.main').window
    dialog = gtk.MessageDialog(parent, gtk.DIALOG_DESTROY_WITH_PARENT,
            gtk.MESSAGE_WARNING, gtk.BUTTONS_OK)
    dialog.set_icon(OPENERP_ICON)
    dialog.set_markup('<b>%s</b>\n\n%s' % (to_xml(title),to_xml(msg)))
    dialog.show_all()
    dialog.run()
    parent.present()
    dialog.destroy()
    return True

def sur(msg, parent=None):
    if not parent:
        parent=service.LocalService('gui.main').window
    sur = glade.XML(terp_path("openerp.glade"), "win_sur",gettext.textdomain())
    win = sur.get_widget('win_sur')
    win.set_transient_for(parent)
    win.show_all()
    l = sur.get_widget('lab_question')
    l.set_text(msg)

    if not parent:
        parent=service.LocalService('gui.main').window
    win.set_transient_for(parent)
    win.set_icon(OPENERP_ICON)

    response = win.run()
    parent.present()
    win.destroy()
    return response == gtk.RESPONSE_OK

def sur_3b(msg, parent=None):
    sur = glade.XML(terp_path("openerp.glade"), "win_quest_3b",gettext.textdomain())
    win = sur.get_widget('win_quest_3b')
    l = sur.get_widget('label')
    l.set_text(msg)

    if not parent:
        parent=service.LocalService('gui.main').window
    win.set_transient_for(parent)
    win.set_icon(OPENERP_ICON)

    response = win.run()
    parent.present()
    win.destroy()
    if response == gtk.RESPONSE_YES:
        return 'ok'
    elif response == gtk.RESPONSE_NO:
        return 'ko'
    elif response == gtk.RESPONSE_CANCEL:
        return 'cancel'
    else:
        return 'cancel'

def ask(question, parent=None):
    dia = glade.XML(terp_path('openerp.glade'), 'win_quest', gettext.textdomain())
    win = dia.get_widget('win_quest')
    label = dia.get_widget('label1')
    label.set_text(question)
    entry = dia.get_widget('entry')

    if not parent:
        parent=service.LocalService('gui.main').window
    win.set_transient_for(parent)
    win.set_icon(OPENERP_ICON)

    response = win.run()
    parent.present()
    win.destroy()
    if response == gtk.RESPONSE_CANCEL:
        return None
    else:
        return entry.get_text()

def concurrency(resource, id, context, parent=None):
    dia = glade.XML(common.terp_path("openerp.glade"),'dialog_concurrency_exception',gettext.textdomain())
    win = dia.get_widget('dialog_concurrency_exception')

    if not parent:
        parent=service.LocalService('gui.main').window
    win.set_transient_for(parent)
    win.set_icon(OPENERP_ICON)

    res= win.run()
    parent.present()
    win.destroy()

    if res == gtk.RESPONSE_OK:
        return True
    if res == gtk.RESPONSE_APPLY:
        obj = service.LocalService('gui.window')
        obj.create(False, resource, id, [], 'form', None, context,'form,tree')
    return False

def open_file(value, parent):
    filetype = {}
    if options['client.filetype']:
        if isinstance(options['client.filetype'], str):
            filetype = eval(options['client.filetype'])
        else:
            filetype = options['client.filetype']
    root, ext = os.path.splitext(value)
    cmd = False
    if ext[1:] in filetype:
        cmd = filetype[ext[1:]] % (value)
    if not cmd:
        cmd = file_selection(_('Open with...'),
                parent=parent)
        if cmd:
            cmd = cmd + ' %s'
            filetype[ext[1:]] = cmd
            options['client.filetype'] = filetype
            options.save()
            cmd = cmd % (value)
    if cmd:
        pid = os.fork()
        if not pid:
            pid = os.fork()
            if not pid:
                prog, args = cmd.split(' ', 1)
                args = [os.path.basename(prog)] + args.split(' ')
                try:
                    os.execvp(prog, args)
                except:
                    pass
            time.sleep(0.1)
            sys.exit(0)
        os.waitpid(pid, 0)


# Color set

colors = {
    'invalid':'#ff6969',
    'readonly':'#eeebe7',
    'required':'#d2d2ff',
    'normal':'white'
}



# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:

