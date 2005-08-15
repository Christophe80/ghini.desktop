#
# editors module
#

import sys, os, os.path
import re
import copy

import bauble
import gtk

from sqlobject.sqlbuilder import *
from sqlobject import *


from tables import tables, BaubleTable
import utils

from utils.debug import debug
debug.enable = False

# TODO: if the last column is made smaller from draggin the rightmost part
# of the header then automagically reduce the size of  the dialog so that the 
# there isn't the extra junk past the, and i guess do the same to the leftmost
# side of the the first column

# TODO: need some type of smart dialog resizing like when columns are added
# change the size of the dialog to fit unless you get bigger than the screen
# then turn on the scroll bar, and something similar for adding rows 

# FIXME: everytime you open and close a TreeViewEditorDialog the dialog
# get a little bigger, i think the last column is creeping

def createColumnMetaFromTable(table):
    """
    return a MetaViewColumn class built from an sqlobj
    """

    meta = ViewColumnMeta()
    #for name, col in table.sqlmeta._columnDict.iteritems():
    for name, col in table.sqlmeta.columns.iteritems():
        if name[0] == "_":  continue # _means private
        col_meta =  ViewColumnMeta.Meta()
        if name.endswith("ID"):
            col_meta.foreign = True
            name = name[:-2]
        col_meta.header = name 
        col_meta.type = type(col)
        # TODO: other validators that are easy, like floats
        # and possibly dates, in fact, i don't think dates work
        # at all right now
        if col_meta.type == SOIntCol:
            col_meta.validate = lambda x: int(x)
        if col._default == NoDefault:
            col_meta.default = col._default # the default value from the table
            col_meta.visible = True
            col_meta.required = True
        meta[name] = col_meta
    
    for join in table.sqlmeta.joins:
        if type(join) == SingleJoin:
            name = join.joinMethodName
            if name[0] == "_":  continue # _means private
            col_meta.header = name
            col_meta =  ViewColumnMeta.Meta()
            col_meta.type = type(join)
            col_meta.join = True
            meta[name] = col_meta    
    return meta


def validate_int(value):
    v = int(value)
    return v


def validate_accession(value):
    # should check the value fits the format of an accession number
    return value


class TableMeta:
    """
    hold information about the table we will be editing with the table editor
    """
    def __init__(self):
        self.foreign_keys = []
    

class ViewColumnMeta(dict):
    """
    contains a dictionary of Meta classes which store information
    about the different columns in the view
    """
    
    class Meta:
        def __init__(self, header="", visible=False, foreign=False, 
                     width=50, default=None, editor=None, required=False,
                     getter=None):
            self.header = header
            self.visible = visible
            self.foreign = foreign
            self.width = width # the default width for all columns
            self.default = default
            self.editor = editor
            self.required = required
            self.getter = getter            
            
            # a dummy validate function
            self.validate = lambda x: x
            
            
    # set column meta, value[0] = name, value[1] = visible, value[2] = foreign
    def __setitem__(self, item, value):
        if type(value) == dict:
            dict.__setitem__(self, item, ViewColumnMeta.Meta(**value))
        else: dict.__setitem__(self, item, value)
        

    def _set_headers(self, headers):
        for col, header in headers.iteritems():
            self[col].header = header
    headers = property(fset=_set_headers)

        
    
class ModelDict(dict):
    """
    a dictionary representation of an SQLObject used for storing table
    rows in a gtk.TreeModel
    dictionary values are only stored in self if they are accessed, this
    saves on database queries lookups (i think, should test). this also
    means that when we retrieve the dictionary to commit the values then
    we only get those values that have been accessed
    """
    def __init__(self, row, meta=None, defaults={}):
        # if row is an instance of BaubleTable then get the values
        # from the instance else check that the items are valid table
        # attributes and don't let the editors set attributes that 
        # aren't valid
        
        # if row is not an instance then make sure
        self.isinstance = False
        if isinstance(row, BaubleTable):
            self.isinstance = True
            self['id'] = row.id # always keep the id
        elif not issubclass(row, BaubleTable):
            msg = 'row shoud be either an instance or class of BaubleTable'
            raise ValueError('ModelDict.__init__: ' + msg)
            
        #if row is not None and not isinstance(row, BaubleTable):
        #    raise ValueError('ModelDict.__init__: row is not an instance')
        
        self.row = row # either None or an instance of BaubleTable
        self.defaults = defaults or {}
        self.meta = meta


    
    def __contains__(self, item):
        """
        this causes the 'in' operator and has_key to behave differently,
        e.g. 'in' will tell you if it exists in either the dictionary
        or the table while has_key will only tell you if it exists in the 
        dictionary, this is a very important difference
        """
        if self.has_key(item):
            return True
        elif self.row is not None: 
            return hasattr(self.row, item)
        else: 
            return False
        #if self.row is not None:
        #    return hasattr(self.row, item)
        #else: self.has_key(item)


    def __getitem__(self, item):
        """
        get items from the dict
        if the item does not exist then we create the item in the dictionary
        and set its value from the default or to None
        """
    
        if self.has_key(item): # use has_key to avoid __contains__
            return self.get(item)

        # else if row is an instance then get it from the table
        v = None
        if self.isinstance:
            if self.meta[item].getter is not None:
                v = self.meta[item].getter(self.row)
            else: # we want this to fail is item doesn't exist in row
                v = getattr(self.row, item)
            if v is None and item in self.defaults:
                v = self.defaults[item]
        else:
            # else not an instance so at least make sure that the item
            # is an attribute in the row, should probably validate the type
            # depending on the type of the attribute in row
            if not hasattr(self.row, item):
                msg = '%s has not attribute %s' % (self.row.__class__, item)
                raise KeyError('ModelDict.__getitem__: ' + msg)
            if item in self.defaults:
                v = self.defaults[item]
            else:
                v = None
        self[item] = v
        return v
       
        


#
# editor interface
#
class TableEditor(object):

    standalone = True
    
    def __init__(self, table, select=None, defaults={}):
        self.defaults = copy.copy(defaults)
        self.table = table
        self.select = select
        
        
    def start(self): pass
        #raise NotImplementedError, 'TableEditor.start() not implemented'
        
        
#    def commit_changes(self):
#        raise NotImplementedError, "TableEditor.commit_changes not implemented"

#
# editor interface that opens a dialog
#
class TableEditorDialog(TableEditor, gtk.Dialog):
    

    def __init__(self, table, title="Table Editor", parent=None, select=None, defaults={}):
        TableEditor.__init__(self, table, select, defaults)
        gtk.Dialog.__init__(self, title, parent, 
                            gtk.DIALOG_MODAL | gtk.DIALOG_DESTROY_WITH_PARENT, 
                            (gtk.STOCK_OK, gtk.RESPONSE_OK, 
                             gtk.STOCK_CANCEL, gtk.RESPONSE_CANCEL))
        self.connect("response", self.on_response)

                              
#    def commit_changes(self):
#        raise NotImplementedError, "TableEditorDialog.commit_changes not implemented"

    def start(self, block=False):
        #TableEditorDialog.
        #super(TableEditorDialog, self).start()
        if block:
            self.run()
        else: self.show()
            
        
    def on_response(self, widget, response, data=None):
        super(TableEditorDialog, self).on_response()


#
# TreeViewEditorDialog
# a spreadsheet style editor
#
# TODO:
# (1) make this a proper abstract class
# (2) ability to attach some sort of validator on the column
# which will always ensure that whatever is entered is of the correct format
# and would possible even complete some things for you like the "." in the
# middle of an accessions
# (3) should somehow check which columns have default values and which
# don't and treat them as required columns, so you can't change the visibility
# and can go to the next row having with out editing them
# (4) should have a label at the top which give information about what's
# being edited and what could be wrong ala eclipse
class TreeViewEditorDialog(TableEditorDialog):
    """the model for the view in this class only has a single column which
    is a Table class which is really just a dict. each value in the dict
    relates to a column in the tree but
    this allows us to refer to the columns by name rather than by column
    number    
    """    
    visible_columns_pref = None
    column_width_pref = None
    default_visible_list = []

    
    def __init__(self, table, title="Table Editor", parent=None, select=None, defaults={}):
        TableEditorDialog.__init__(self, table, title=title, parent=parent, select=select,
                                   defaults=defaults)      
        self.view = None        
        self.columns = {} # self.columns[name] = gtkcolumn
        self.dirty = False
        self.column_meta = createColumnMetaFromTable(table)
        self.table_meta = TableMeta()

        
    def start(self, block=False):
        # this ensures that the visibility is set properly in the meta before
        # before everything is created
        print 'entered TreeViewEditorDialog.start()'
        if self.visible_columns_pref is not None:
            if not self.visible_columns_pref in bauble.prefs:
                bauble.prefs[self.visible_columns_pref] = self.default_visible_list
            self.set_visible_columns_from_prefs(self.visible_columns_pref)
        print 'TreeViewEditorDialog.start()'
        self.create_gui()
        super(TreeViewEditorDialog, self).start(block)
        print 'leaving TreeViewEditorDialog.start()'
    
        

    def foreign_does_not_exist(self, name, value):
        """
        this is intended to be overridden in a subclass to do something
        interesting if the foreign key doesn't exist
        """
        msg = "%s does not exist in %s" % (value, name)
        utils.message_dialog(msg, gtk.MESSAGE_ERROR)
        
    # this is used to indicate that the last row is a valid row
    # or it is one that was added automatically but never used
    dummy_row = False
    
    
    def set_view_model_value(self, path, colname, value):
        model = self.view.get_model()
        i = model.get_iter(path)
        row = model.get_value(i, 0)
        row[colname] = value


    def validate(self, colname, value):
        #type
        return value
    
    
    def on_completion_match_selected(self, completion, model, iter, 
                                     path, colname):
        """
        all foreign keys should use entry completion so you can't type in
        values that don't already exists in the database, therefore, allthough
        i don't like it the view.model.row is set here for foreign key columns
        and in self.on_renderer_edited for other column types                
        """        
        id = model.get_value(iter, 1)
        name = model.get_value(iter, 0)
        
        model = self.view.get_model()
        self.set_view_model_value(path, colname, [id, name])
    

    def on_cell_key_press(self, widget, event, path, colname):
        """
        handled TreeView navigation
        """
        keyname = gtk.gdk.keyval_name(event.keyval)
        path, col = self.view.get_cursor()
        if keyname == 'Return':
            # start the editor for the cell if there is one
            meta = self.column_meta[colname]
            if hasattr(meta, 'editor') and meta.editor is not None:
                self.set_sensitive(False)
                model = self.view.get_model()
                it = model.get_iter(path)
                row = model.get_value(it,0)
                v = meta.editor(select=row[colname]).start() # this blocks
                self.set_view_model_value(path, colname, v)
                self.set_sensitive(True)
                self.set_dirty(True)
        elif keyname == "Up" and path[0] != 0:            
            self.move_cursor_up(path, col)
        elif keyname == "Down" and path[0] != len(self.view.get_model()):
            # TODO: check if the entry completion is open and if so then
            # set the focus to the completions, eles move the cursor down
            print "%s - %s" % (str(path), str(col))   
            # current_entry is set in editing_started and removed in editing_done
            if self.current_entry is not None: 
                comp = self.current_entry.get_completion()                
            else: self.move_cursor_down(path, col)
        elif keyname == "Left":
            self.move_cursor_left(path, col)
            pass
        elif keyname == "Right":
            self.move_cursor_right(path, col)
            pass
        elif keyname == "Tab":            
            columns = self.view.get_columns()
            ncols = len(columns)
            # if last column and not last row,
            # TODO: this doesn't
            # work anymore now that we create all rows instead of just
            # the visible ones, we need to get the index of the highest
            # visible row
            if columns[ncols-1] == col and len(self.view.get_model()) != ncols:
                newpath = path[0]+1, 
                self.view.set_cursor_on_cell(newpath, columns[0], None, True)
            else: self.move_cursor_right(path, col) # else moveright
                

    def move_cursor_right(self, path, fromcol):
        """
        """
        newcol = fromcol
        columns = self.view.get_columns()
        fromcol_index = 100 # 100 is an arbitrary max
        for i in xrange(0, len(columns)): # find the columns index            
            if columns[i] == fromcol: fromcol_index = i
            if columns[i].get_visible() and i > fromcol_index:
                newcol = columns[i]
                break        
        self.view.set_cursor_on_cell(path, newcol, None, True)

        
    def move_cursor_left(self, path, fromcol):
        """
        """
        newcol = fromcol
        columns = self.view.get_columns()
        fromcol_index = -1
        for i in xrange(len(columns)-1, 0, -1): # iterate in reverse
            if columns[i] == fromcol: fromcol_index = i
            if columns[i].get_visible() and i < fromcol_index:
                newcol = columns[i]
                break
        self.view.set_cursor_on_cell(path, newcol, None, True)

    
    def move_cursor_up(self, path, col):
        newpath = path[0]-1, 
        self.view.set_cursor_on_cell(newpath, col, None, True)
        #renderer.stop_emit_by_name("key-press-event")

    
    def move_cursor_down(self, path, col):
        newpath = path[0]+1, 
        self.view.set_cursor_on_cell(newpath, col, None, True)
        #renderer.stop_emit_by_name("key-press-event")


    def on_renderer_toggled(self, renderer, path, colname):
        active = not renderer.get_active()
        self.set_view_model_value(path, colname, active)
        
        
    def set_ok_sensitive(self, sensitive):
        ok_button = self.action_area.get_children()[1]
        ok_button.set_sensitive(sensitive)
        
        
    def on_renderer_edited(self, renderer, path, new_text, colname):
        """
        signal called when editing is finished on a cell
        retrieves the value in the cell, validates it and sets the value
        in the model
        """
         
        #print 'on_renderer_edited:'
        #print ' -- new: "%s"' % str(new_text)
        new_text = new_text.strip() # crash on None? is new_text ever None?
        model = self.view.get_model()
        it = model.get_iter(path)
        row = model.get_value(it, 0)
        #print ' -- %s: "%s"' % (colname, str(row[colname]))
        
        # compare everything by string b/c if the value is an object
        # then the comparison doesn't work
        # FIXME: this workds for now but we need to make __cmp__ methods 
        # for anything that might be in the model, possibly only need one
        # for BaubleTable, this works for 
        if colname in row and str(row[colname]) == str(new_text):
            #print 'no change'
            return
        
        #if new_text == None: return
#        if new_text == None or new_text == "":
#            return        
        if not self.column_meta[colname].foreign:
            v = None
            if not new_text == "": # set v and validate if not empty
                v = self.column_meta[colname].validate(new_text)
            self.set_view_model_value(path, colname, v)
        else:
            # need to somehow get the id from the text value, is it possible?
            # if it is a foreign key then the row in the model should be
            # set when a match is selected in the EntryCompletion,
            # see on_completion_match_selected
            # *** i don't really like this, i would prefer to set the model
            # in one place
            pass

        self.set_dirty(True)
        #self.dirty = True # something has changed
        #self.set_ok_sensitive(True)
#        self.view.check_resize() # ???????

        # edited the last row so add a new one,
        # i think this may a bit of a bastardization of path but works for now
        model = self.view.get_model()
        if new_text != "" and int(path) == len(model)-1:
            self.add_new_row()
            self.dummy_row = True
            
            
    def set_dirty(self, dirty=True):
        self.dirty = dirty
        self.set_ok_sensitive(dirty)
            
            
    def on_editing_started(self, cell, editable, path, colname):

        if self.column_meta[colname].editor:
            editable.set_property('editable', False)
        
        if isinstance(editable, gtk.Entry):            
            editable.connect("key-press-event", self.on_cell_key_press, 
                             path, colname)
            # set up a validator on the col depending on the sqlobj.column type
            editable.connect("insert-text", self.on_insert_text, 
                             path, colname)
            editable.connect("editing-done", self.on_editing_done)
            self.current_entry = editable
            # if not a foreign key then validate, foreign keys can only
            # be entered from existing values and so don't need to
            # be validated
            #if not self.column_meta[colname].foreign:
            #    if self.column_meta[colname].                


    def on_editing_done(self, editable, data=None):
        """
        not editing anymore, set current entry to None
        """
        self.current_entry = None
        
        
    def on_validate_date(self, entry, text, length, position):
        print "validate date"
        full_text = entry.get_text()

        
    def on_validate_int(self, entry, text, length, position):
        print "validate int"
        try:
            i = int(text)
        except ValueError:
            entry.stop_emission("insert-text")


    def on_insert_text(self, entry, text, length, position, path, colname):
        """
        handle text filtering/validation and completions
        """
        # TODO: the problem is only validates on letter at a time
        # we need to have a format string which is inserted
        # in the entry before typeing starts and fills in the gap
        # as the user types
        try:
            self.column_meta[colname].validate(text)
        except ValueError:
            entry.stop_emission("insert_text")
        
        full_text = entry.get_text()
        if len(full_text) > 2: # add completions
            entry_completion = entry.get_completion()
            model, maxlen = self.get_completions(full_text, colname)
            if entry_completion is None and model is not None:
                entry_completion = gtk.EntryCompletion()
                entry_completion.set_minimum_key_length(2)
                entry_completion.set_text_column(0)
                entry_completion.connect("match-selected", 
                                         self.on_completion_match_selected, 
                                         path, colname)
                #entry_completion.set_inline_completion(True)
                #entry_completion.set_match_func(self.match_func, None)
                entry.set_completion(entry_completion)

            if entry_completion is None and self.column_meta[colname].foreign:
                raise Exception("No completion defined for column %s" % colname)
            
            if entry_completion is not None:
                entry_completion.set_model(model)

    # Assumes that the func_data is set to the number of the text column in the
    # model.
    def match_func(self, completion, key, iter, column, data=None):
        model = completion.get_model()
        text = model.get_value(iter, column)
        if text.startswith(key):
          return True
        return False
        
    
    def on_cursor_changed(self, view, data=None):
        path, column = self.view.get_cursor()
        print "on_cursor_changed: %s, %s" %(path, column)
        return
        print "BLOCK"
        view.handler_block(self.cursor_changed_id)
        #if stop
        view.set_cursor(path, column, True)
        print "UN block"
        view.handler_unblock(self.cursor_changed_id)
        #self.grab_focus(entry)


    def on_column_menu_toggle(self, item, colname=None):
        visible = item.get_active()
        self.columns[colname].set_visible(visible)
        
        # could do this with a property notify signal
        #self.column_meta[colname].visible = visible
        self.view.resize_children()


    def on_column_changed(self, treeview, data=None):
        """
        keep up with the order of the columns to make key navigation
        easier
        NOTE: i'm not sure what i'm talking about here, i think this may be
        an old function i don't need anymore
        """
        #print "on_column_changed"
        pass
    
    
    def on_response(self, widget, response, data=None):
        #super(TreeViewEditorDialog, self).on_response()
        self.store_visible_columns() # save preferences before we do anything
        self.store_column_widths()
        if response == gtk.RESPONSE_OK:
            #if self.commit_changes():
            # NOTE: i don't understand why we can't call commit_changes 
            # on self
            #if TreeViewEditorDialog.commit_changes(self):                
            if self.commit_changes():
                #
                # TODO: shouldn't destroy self here if on_response is
                # called before run exits, i think this will cause leaks
                # or problems b/c the rest of run won't know what's been
                # destroyed
                #
                self.destroy() # successfully commited
        elif response == gtk.RESPONSE_CANCEL and self.dirty:            
            msg = "Are you sure? You will lose your changes."
            if utils.yes_no_dialog(msg):
                self.destroy()
        else: # cancel, not dirty
            self.destroy()
        return False
        #super(TreeViewEditorDialog, self).on_response(widget, response, data)
        #TreeViewEditorDialog.on_response(self, widget, response, data)
        
        
    def get_values_from_view(self):
        """
        used by commit_changes to get the values from a table so they
        can be commited to the database, this version of the function
        removes the values with None as the value from the row, i thought
        this was necessary but now i don't, in fact it may be better in
        case you want to explicitly set things null
        """
        # TODO: this method needs some love, there should be a more obvious
        # way or at least simpler way of return lists of values
        model = self.view.get_model()
        values = []
        for item in model:
            # copy it so we dont change the data in the model
            # TODO: is it really necessary to copy here
            temp_row = copy.copy(item[0]) 
            for name, value in item[0].iteritems():                
                # del the value if they are none, have to do this b/c 
                # we don't want to store None in a row without a default
                if value is None:
                    del temp_row[name]
                if type(value) == list and type(value[0]) == int:
                    temp_row[name] = value[0] # is an id, name pair
                    #else: # it is a list but we assume the [0] is 
                    # a table and [1] is a dict of value to commit, 
                    # we assume this is here because we need to set the 
                    # foreign key in the subtable to the id of the current
                    # row after it is commited and then commit the subtable
                    # there has to be a better way than this
                        
            values.append(temp_row)
            
        if self.dummy_row:
            del values[len(model)-1] # the last one should always be empty
        return values      
        
        
    def commit_changes(self):
        """
        commit any change made in the table editor
        """        
        # TODO: do a map through the values returned from get_tables_values
        # and check if any of them are lists in the (table, values) format
        # if they are then we need pop the list from the values and commit
        # the current table, set the foreign key of the sub table and commit 
        # it
        # TODO: if i don't set the connection parameter when i create the
        # table then is it really using the transaction, it might be if 
        # sqlhub.threadConnection is set to the transaction
        values = self.get_values_from_view()
        old_conn = sqlhub.getConnection()
        trans = old_conn.transaction()
        sqlhub.threadConnection = trans
        for v in values:
            foreigners = {}
            # first pop out columns in table_meta.foreign_keys so we can
            # set their foreign key id later
            for col, col_attr in self.table_meta.foreign_keys:
                # use has key to check the dict and not the table, 
                # see ModelDict.__contains__
                if v.has_key(col): 
                    foreigners[col] = v.pop(col)
            try:
                if 'id' in v:# updating row
                    t = self.table.get(v["id"])
                    del v["id"]
                    t.set(**v)
                else: # adding row
                    t = self.table(**v)
                #print 'foreign: ' + str(foriegners)
                # set the foreign keys id of the foreigners
                for col, col_attr in self.table_meta.foreign_keys:
                    if col in foreigners:
                        c = foreigners[col]
                        c.set(**{col_attr: t.id})
                    
            except Exception, e:
                msg = "Could not commit changes.\n" + str(e)
                trans.rollback()
                sqlhub.threadConnection = old_conn
                utils.message_dialog(msg, gtk.MESSAGE_ERROR)
                return False
        trans.commit()
        sqlhub.threadConnection = old_conn
        return True
    
    
    def toggle_cell_data_func(self, col, cell, model, iter, column_name):
        """
        cell data func for toggle cell renderers
        """
        v = model.get_value(iter, 0)
        row = v[column_name]
        if row is None:
            # this should really get the default value from the table
            cell.set_property('inconsistent', False) 
        else:
            cell.set_property('active', row)
            
    
    def text_cell_data_func(self, col, cell, model, iter, colname):
        """
        cell data func for cell renderers other than toggle
        """
        row = model.get_value(iter, 0)
        #if colname not in row: return # this should never happen
        value = row[colname]
        
        if value is None: # no value in model
            cell.set_property('text', None)
        elif type(value) == list: # if a list then row[1] is the id
            cell.set_property('text', value[1])
        else: 
            # just plain text in model column or something convertible 
            # to string like a table row
            cell.set_property('text', str(value))                    


    def create_toolbar(self):
        """
        TODO: should make those columns that can't be null and don't
        have a default value, i.e. required columns show in the menu
        but they should be greyed out so you can't turn them off
        """
        self.toolbar = gtk.Toolbar()
        col_button = gtk.MenuToolButton(None, label="Columns")
        menu = gtk.Menu()
        # TODO: would rather sort case insensitive
        for name, meta in sorted(self.column_meta.iteritems()):
            # no mnemonics
            item = gtk.CheckMenuItem(meta.header.replace('_', '__')) 
            if meta.default == NoDefault:
                item.set_sensitive(False)
            item.set_active(meta.visible)
            item.connect("toggled", self.on_column_menu_toggle, name)
            menu.append(item)
        menu.show_all()
        col_button.set_menu(menu)
        self.toolbar.insert(col_button, 0)            
            

    def create_gui(self):
        vbox = gtk.VBox(False)
        
        self.create_toolbar()        
        vbox.pack_start(self.toolbar, fill=False, expand=False)
        
        self.create_tree_view()
        sw = gtk.ScrolledWindow()        
        sw.set_policy(gtk.POLICY_NEVER, gtk.POLICY_AUTOMATIC)
        sw.add(self.view)
        vbox.pack_start(sw)
        #vbox.pack_start(self.view)
        
        self.vbox.pack_start(vbox)
        
        # get the size of all children widgets
        width, height = self.size_request()
        #print str(width) + " " + 

        col_widths = bauble.prefs[self.column_width_pref]
        if col_widths is not None:
            total = sum(col_widths.values())
        #self.set_geometry_hints(min_width=total)
        self.set_default_size(-1, 300) # 10 is a guestimate at border width
        
        # set ok button insensitive
        ok_button = self.action_area.get_children()[1]
        ok_button.set_sensitive(False)
        
        self.show_all()
        #self.resize_children()
        #print self.size_request()
        #print tuple(self.allocation)
        
        
    def create_view_column(self, name, meta):
        """
        create the tree view column from the meta
        """
        r = None
        column = None
        # create the renderer and model if it needs it
        if meta.type == SOBoolCol:
            r = gtk.CellRendererToggle()
        elif meta.type == SingleJoin: 
            # TODO: this should be removed, we don't edit any single joins 
            # directory i don't think, though it might not be a bad idea
            # to do so            
            r.set_property('has_entry', False)
            r.set_property("text-column", 0)
            data = ['----------', 'Edit', '----------', 'Delete']
            model = gtk.ListStore(str)
            for d in data: model.append([d])
            r.set_property("model", model)
        elif hasattr(self.table, "values") and name in self.table.values:
            r = gtk.CellRendererCombo()
            r.set_property("text-column", 0)
            model = gtk.ListStore(str, str)            
            for v in self.table.values[name]:
                model.append(v)
            r.set_property("model", model)
        else: 
            r = gtk.CellRendererText()
            
        # create the column    
        # replace so the '_' so its not interpreted as a mnemonic
        column = gtk.TreeViewColumn(meta.header.replace("_", "__"), r)
        
        # specific renderer config and overrides
        if type(r) == gtk.CellRendererToggle:
            r.connect("toggled", self.on_renderer_toggled, name)
            column.set_cell_data_func(r, self.toggle_cell_data_func, name)
        else:
            r.set_property("editable", True)
            r.connect("editing_started", self.on_editing_started, name)
            column.set_cell_data_func(r, self.text_cell_data_func, name)
            if meta.editor is None: # the editor will set the value
                r.connect("edited", self.on_renderer_edited, name)
                
        # generic column config
        column.set_min_width(50)
        column.set_clickable(True)
        column.set_resizable(True)
        column.set_sizing(gtk.TREE_VIEW_COLUMN_FIXED)
        column.set_reorderable(True)
        column.set_visible(meta.visible)
        width_dict = bauble.prefs[self.column_width_pref]
        if width_dict is not None and name in width_dict:
            column.set_fixed_width(width_dict[name])
        column.name = name # .name is my own data, not part of gtk
        # notify when the column width property is changed
        
        column.connect("notify::width", self.on_column_property_notify, name)
        column.connect("notify::visible", self.on_column_property_notify, name)
        return column


    def on_column_property_notify(self, widget, property, name):
        """
        synchronizes property changes with columns and column_meta
        """
        value = widget.get_property(property.name)
        meta = self.column_meta[name]
        if hasattr(meta, property.name):
            setattr(meta, property.name, value)


    def create_tree_view(self):
        """
        create the main tree view
        """
        # create the columns from the meta data
        for name, meta in self.column_meta.iteritems(): 
            self.columns[name] = self.create_view_column(name, meta)
        
        self.view = gtk.TreeView(gtk.ListStore(object))
        self.view.set_headers_clickable(False)

        # create the model from the tree view and add rows if a
        # selectresult is passed
        if self.select is not None:
            for row in self.select:
                self.add_new_row(row)
        else:
            self.add_new_row()
            
        # enter the columns from the visible list, the visibility
        # should already have been set before creation from the prefs
        visible_list = ()
        if self.visible_columns_pref in bauble.prefs:
            visible_list = list(bauble.prefs[self.visible_columns_pref][:])
            visible_list.reverse()
            for name in visible_list:
                if name in self.columns:
                    self.view.insert_column(self.columns[name], 0)
        
        # append the rest of the column to the end
        for name in self.columns:
            if name not in visible_list:
                self.view.append_column(self.columns[name])

        # now that all the columns are here, let us know if anything 
        # changes
        self.view.connect("columns-changed", self.on_column_changed)


    def add_new_row(self, row=None):
        model = self.view.get_model()
        if model is None: raise Exception("no model in the row")
        if row is None:
            row = self.table
        model.append([ModelDict(row, self.column_meta, self.defaults)])

        
    def get_completions(self, text, colname):
        """
        return a list of completions relative to the current input and
        the length of the longest completion
        does nothing by default but is intended to be extended by other classes
        """
        #raise NotImplementedError
        return None, 0


    def set_visible_columns_from_prefs(self, prefs_key):
        """
        load the visible column from the preferences key and reset the visible
        attribute on each column
        this doesn't change the visibility in the tree view so the
        method name may be misleading
        """        
        visible_columns = bauble.prefs[prefs_key]
        if visible_columns is None: return
        # reset all visibility from prefs
        for name, meta in self.column_meta.iteritems():
            if name in visible_columns:
                meta.visible = True                    
            elif not meta.required: 
                meta.visible = False

    
    def store_column_widths(self):
        """
        store the column widths as a dict in the preferences
        """
        if self.column_width_pref is None:
            raise Exception("TreeViewEditorDialog.store_column_widths: " \
                            "column_width_pref not set")
        width_dict = {}
        for name, meta in self.column_meta.iteritems():
            width_dict[name] = meta.width
        
        
        #for col in self.view.get_columns():            
        #    if col.get_visible():
        #        width_dict[col.name] = col.get_width()                
        pref_dict = bauble.prefs[self.column_width_pref]
        if pref_dict is None:
            bauble.prefs[self.column_width_pref] = width_dict
        else: 
            pref_dict.update(width_dict)
            bauble.prefs[self.column_width_pref] = pref_dict


    def store_visible_columns(self):
        """
        get the currently visible columns and store them to the preferences
        """
        visible = []
        for c in self.view.get_columns():
            if c.get_visible():
                visible.append(c.name)
        bauble.prefs[self.visible_columns_pref] = visible
                

class Singleton(dict):
        _instance = None
        def __new__(cls, *args, **kwargs):
            if not cls._instance:
                cls._instance = super(Singleton, cls).__new__(
                                   cls, *args, **kwargs)
            return cls._instance              


class _editors(Singleton):
    
    _all = [] # for other access
    _by_table = {} # for __getitem__
    _by_name = {}  # fir __getattr__
    _initialized = False
                   
    @classmethod
    def _init(cls):
        if cls._initialized: 
            return
        modules = []
        path, name = os.path.split(__file__)
        if path.find("library.zip") != -1: # using py2exe
            pkg = "editors"
            zipfiles = __import__(pkg, globals(), locals(), [pkg]).__loader__._files 
            x = [zipfiles[file][0] for file in zipfiles.keys() if pkg in file]
            s = '.+?' + os.sep + pkg + os.sep + '(.+?)' + os.sep + '__init__.py[oc]'
            rx = re.compile(s.encode('string_escape'))
            for filename in x:
                m = rx.match(filename)
                if m is not None:
                    modules.append('%s.%s' % (pkg, m.group(1)))                        
        else:        
            for d in os.listdir(path):
                full = path + os.sep + d 
                if os.path.isdir(full) and os.path.exists(full + os.sep + "__init__.py"):
                    modules.append("editors." + d)
    
        for m in modules:
            m = __import__(m, globals(), locals(), ['editors'])
        cls.initialized = True

    @classmethod
    def register(cls, editor, table=None):        
        """
        editors are registered by the table they edit
        """        
        print "registering %s editor " % editor.label
        import tables
        #print tables.BaubleTable
        if table is not None and not issubclass(table, tables.BaubleTable):
            msg = 'editors.register(): table must be a subclass of BaubleTable'
            raise ValueError(msg)
        
        cls._all.append(editor)        
        cls._by_name[editor.__name__] = editor
        if table is not None: # doesn't work on any particular table
            cls._by_table[table.__name__] = editor     
    
   
    @classmethod
    def all(cls):
        return cls._all
        
        
    @classmethod
    def __contains__(cls, item):
        """
        check by table, completely different than by editor name
        """
        return cls._by_table.has_key(item)
        
    @classmethod
    def __getitem__(cls, item):
        import tables
        if type(item) == str:
            return cls._by_table[item]
        elif not issubclass(item, tables.BaubleTable):
            msg = 'items must be looked up by table class or class name'
            raise ValueError('editors.__getitem__():' + msg)
        return cls._by_table[item.__name__]

   
       
editors = _editors()
editors.init()



    


                             


        

    


        
