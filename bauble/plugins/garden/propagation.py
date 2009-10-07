# -*- coding: utf-8 -*-
#
# propagation module
#

import sys
import re
import os
import weakref
import traceback
from random import random
from datetime import datetime
import xml.sax.saxutils as saxutils

import gtk
import gobject
from sqlalchemy import *
from sqlalchemy.orm import *
from sqlalchemy.orm.session import object_session
from sqlalchemy.exc import SQLError

import bauble
import bauble.db as db
from bauble.error import check
import bauble.utils as utils
import bauble.paths as paths
import bauble.editor as editor
from bauble.utils.log import debug
from bauble.prefs import prefs
from bauble.error import CommitException
import bauble.types as types
from bauble.view import InfoBox, InfoExpander, PropertiesExpander, \
     select_in_search_results, Action


prop_type_values = {u'Seed': _("Seed"),
                    u'UnrootedCutting': _('Unrooted cutting'),
                    u'Other': _('Other')}


# TODO: create an add propagation field to an accession context menu


class Propagation(db.Base):
    """
    Propagation
    """
    __tablename__ = 'propagation'
    #recvd_as = Column(Unicode(10)) # seed, urcu, other
    #recvd_as_other = Column(UnicodeText) # ** maybe this should be in the notes
    prop_type = Column(types.Enum(values=prop_type_values.keys()),
                       nullable=False)
    notes = Column(UnicodeText)
    accession_id = Column(Integer, ForeignKey('accession.id'),
                          nullable=False)
    date = Column(types.Date)
    #from bauble.plugins.garden import Accession
    #accessions = relation(Accession, 'accession_id', backref='propagations')
    _cutting = relation('PropCutting',
                      primaryjoin='Propagation.id==PropCutting.propagation_id',
                      cascade='all,delete-orphan', uselist=False,
                      backref=backref('propagation', uselist=False))
    _seed = relation('PropSeed',
                     primaryjoin='Propagation.id==PropSeed.propagation_id',
                     cascade='all,delete-orphan', uselist=False,
                     backref=backref('propagation', uselist=False))

    def _get_details(self):
        if self.prop_type == 'Seed':
            return self._seed
        elif self.prop_type == 'UnrootedCutting':
            return self._cutting
        else:
            raise NotImplementedError

    #def _set_details(self, details):
    #    return self._details

    details = property(_get_details)

    def get_summary(self):
        """
        """
        return str(self)



class PropRooted(db.Base):
    """
    Rooting dates for cutting
    """
    __tablename__ = 'prop_cutting_rooted'
    __mapper_args__ = {'order_by': 'date'}

    date = Column(types.Date)
    quantity = Column(Integer)
    cutting_id = Column(Integer, ForeignKey('prop_cutting.id'), nullable=False)



cutting_type_values = {u'Nodal': _('Nodal'),
                       u'InterNodal': _('Internodal'),
                       u'Other': _('Other')}

tip_values = {u'Intact': _('Intact'),
              u'Removed': _('Removed'),
              u'None': _('None')}

leaves_values = {u'Intact': _('Intact'),
                 u'Removed': _('Removed'),
                 u'None': _('None')}

flower_buds_values = {u'Removed': _('Removed'),
                      u'None': _('None')}

wound_values = {u'No': _('No'),
                u'Single': _('Singled'),
                u'Double': _('Double'),
                u'Slice': _('Slice')}

hormone_values = {u'Liquid': _('Liquid'),
                  u'Powder': _('Powder'),
                  u'No': _('No')}

bottom_heat_unit_values = {u'F': _('\302\260F'),
                           u'C': _('\302\260C')}

class PropCutting(db.Base):
    """
    A cutting
    """
    __tablename__ = 'prop_cutting'
    cutting_type = Column(types.Enum(values=cutting_type_values.keys()),
                          default=u'Other')
    tip = Column(types.Enum(values=tip_values.keys()), nullable=False)
    leaves = Column(types.Enum(values=leaves_values.keys()), nullable=False)
    leaves_reduced_pct = Column(Integer)
    length = Column(Integer)
    length_units = Column(Unicode)

    # single/double/slice
    wound = Column(types.Enum(values=wound_values.keys()), nullable=False)

    # removed/None
    flower_buds = Column(types.Enum(values=flower_buds_values.keys()),
                         nullable=False)

    fungal_soak = Column(Unicode) # fungal soak solution

    #fungal_soak_sec = Column(Boolean)

    hormone = Column(Unicode) # power/liquid/None....solution

    cover_type = Column(Unicode)

    success = Column(Integer) # % of rooting took

    compost = Column(Unicode)
    container = Column(Unicode)
    location = Column(Unicode)
    cover = Column(Unicode) # vispore, poly, plastic dome, poly bag

    bottom_heat_temp = Column(Integer) # temperature of bottom heat

    # F/C
    bottom_heat_unit = Column(types.Enum(values=\
                                             bottom_heat_unit_values.keys()),
                              (nullable=False))
    rooted_pct = Column(Integer)
    #aftercare = Column(UnicodeText) # same as propgation.notes

    propagation_id = Column(Integer, ForeignKey('propagation.id'),
                            nullable=False)

    rooted = relation('PropRooted', cascade='all,delete-orphan',
                        backref=backref('cutting', uselist=False))


class PropSeed(db.Base):
    """
    """
    __tablename__ = 'prop_seed'
    pretreatment = Column(UnicodeText)
    nseeds = Column(Integer)
    date_sown = Column(types.Date)
    container = Column(Unicode) # 4" pot plug tray, other
    compost = Column(Unicode) # seedling media, sphagnum, other

    # covered with #2 granite grit: no, yes, lightly heavily
    covered = Column(Unicode)

    # not same as location table, glasshouse(bottom heat, no bottom
    # heat), polyhouse, polyshade house, fridge in polybag
    location = Column(Unicode)

    # TODO: do we need multiple moved to->moved from and date fields
    moved_from = Column(Unicode)
    moved_to = Column(Unicode)
    moved_date = Column(Unicode)

    germ_date = Column(types.Date)

    nseedling = Column(Integer) # number of seedling
    germ_pct = Column(Integer) # % of germination
    date_planted = Column(types.Date)

    propagation_id = Column(Integer, ForeignKey('propagation.id'),
                            nullable=False)



    def __str__(self):
        # what would the string be...???
        # cuttings of self.accession.species_str() and accessin number
        return repr(self)



class PropagationTabPresenter(editor.GenericEditorPresenter):

    def __init__(self, parent, model, view, session):
        '''
        @param parent: an instance of AccessionEditorPresenter
        @param model: an instance of class Accession
        @param view: an instance of AccessionEditorView
        @param session:
        '''
        super(PropagationTabPresenter, self).__init__(model, view)
        self.parent_ref = weakref.ref(parent)
        self.session = session
        self.view.connect('prop_add_button', 'clicked',
                          self.on_add_button_clicked)
        for prop in self.model.propagations:
            self.create_propagation_box(prop)
            self.view.widgets.prop_tab_box.pack_start(box, expand=False,
                                                      fill=True)
        self.__dirty = False


    def dirty(self):
        debug(self.__dirty)
        debug([p in self.session.dirty for p in self.model.propagations])
        return self.__dirty or \
            True in [p in self.session.dirty for p in self.model.propagations]


    def add_propagation(self):
        # TODO: here the propagation editor doesn't commit the changes
        # since the accession editor will commit the changes when its
        # done...we should merge the propagation created by the
        # PropagationEditor into the parent accession session and
        # append it to the propagations relation so that when the
        # parent editor is saved then the propagations are save with
        # it

        # open propagation editor
        editor = PropagationEditor(parent=self.view.get_window())
        propagation = self.session.merge(editor.start(commit=False))
        self.model.propagations.append(propagation)
        box = self.create_propagation_box(propagation)
        self.view.widgets.prop_tab_box.pack_start(box, expand=False, fill=True)
        self.__dirty = True


    def create_propagation_box(self, propagation):
        """
        """
        hbox = gtk.HBox()
        expander = gtk.Expander()
        hbox.pack_start(expander, expand=True, fill=True)
        alignment = gtk.Alignment()
        hbox.pack_start(alignment, expand=False, fill=False)
        def on_clicked(button, propagation):
            editor = PropagationEditor(model=propagation,
                                       parent=self.view.get_window())
            editor.start(commit=False)
        button = gtk.Button(stock=gtk.STOCK_EDIT)
        self.view.connect(button, 'clicked', on_clicked, propagation)
        alignment.add(button)
        # TODO: add a * to the propagation label for uncommitted propagations
        prop_type = prop_type_values[propagation.prop_type]
        title = ('%(prop_type)s on %(prop_date)s') \
            % dict(prop_type=prop_type, prop_date=propagation.date)
        expander.set_label(title)
        label = gtk.Label(propagation.get_summary())
        expander.add(label)
        hbox.show_all()
        return hbox



    def remove_propagation(self):
        """
        """
        pass


    def on_add_button_clicked(self, *args):
        """
        """
        self.add_propagation()
        self.parent_ref().refresh_sensitivity()



class PropagationEditorView(editor.GenericEditorView):
    """
    """

    _tooltips = {}

    def __init__(self, parent=None):
        """
        """
        super(PropagationEditorView, self).\
            __init__(os.path.join(paths.lib_dir(), 'plugins', 'garden',
                                  'prop_editor.glade'),
                     parent=parent)

    def get_window(self):
        """
        """
        return self.widgets.prop_dialog


    def start(self):
        return self.get_window().run()



class CuttingPresenter(editor.GenericEditorPresenter):

    widget_to_field_map = {'cutting_type_combo': 'cutting_type',
                           'cutting_length_entry': 'length',
                           'cutting_tip_combo': 'tip',
                           'cutting_leaves_combo': 'leaves',
                           'cutting_lvs_reduced_entry': 'leaves_reduced_pct',
                           'cutting_buds_combo': 'flower_buds',
                           'cutting_wound_combo': 'wound',
                           'cutting_fungal_entry': 'fungal_soak',
                           'cutting_hormone_entry': 'hormone',
                           'cutting_location_entry': 'location',
                           'cutting_cover_entry': 'cover',
                           'cutting_heat_entry': 'bottom_heat_temp',
                           'cutting_heat_unit_combo': 'bottom_heat_unit',
                           'cutting_rooted_pct_entry': 'rooted_pct'
                           }

    def __init__(self, parent, model, view, session):
        '''
        @param model: an instance of class Propagation
        @param view: an instance of PropagationEditorView
        '''
        super(CuttingPresenter, self).__init__(model, view)
        self.parent_ref = weakref.ref(parent)
        self.session = session

        # make the model for thie presenter a PropCutting instead of a
        # Propagation
        self.propagation = self.model
        self.propagation._cutting = PropCutting()
        self.model = self.model._cutting
        #self.session.add(self.model)

        self.init_translatable_combo('cutting_type_combo', cutting_type_values,
                                     editor.UnicodeOrNoneValidator())
        self.init_translatable_combo('cutting_tip_combo', tip_values)
        self.init_translatable_combo('cutting_leaves_combo', leaves_values)
        self.init_translatable_combo('cutting_buds_combo', leaves_values)
        self.init_translatable_combo('cutting_wound_combo', wound_values)
        self.init_translatable_combo('cutting_heat_unit_combo',
                                     bottom_heat_unit_values)

        self.refresh_view()

        self.assign_simple_handler('cutting_type_combo', 'cutting_type')
        self.assign_simple_handler('cutting_length_entry', 'length')
        self.assign_simple_handler('cutting_tip_combo', 'tip')
        self.assign_simple_handler('cutting_leaves_combo', 'leaves')
        self.assign_simple_handler('cutting_lvs_reduced_entry',
                                   'leaves_reduced_pct')
        self.assign_simple_handler('cutting_buds_combo', 'flower_buds')
        self.assign_simple_handler('cutting_wound_combo', 'wound')
        self.assign_simple_handler('cutting_fungal_entry', 'fungal_soak',
                                   editor.UnicodeOrNoneValidator())
        self.assign_simple_handler('cutting_hormone_entry', 'hormone',
                                   editor.UnicodeOrNoneValidator())
        self.assign_simple_handler('cutting_location_entry', 'location',
                                   editor.UnicodeOrNoneValidator())
        self.assign_simple_handler('cutting_cover_entry', 'cover',
                                   editor.UnicodeOrNoneValidator())
        self.assign_simple_handler('cutting_heat_entry', 'bottom_heat_temp')
        self.assign_simple_handler('cutting_heat_unit_combo',
                                   'bottom_heat_unit')
        self.assign_simple_handler('cutting_rooted_pct_entry',
                                   'rooted_pct')

        model = gtk.ListStore(object)
        self.view.widgets.rooted_treeview.set_model(model)

        def _rooted_data_func(column, cell, model, treeiter, prop):
            v = model[treeiter][0]
            cell.set_property('text', getattr(v, prop))

        cell = self.view.widgets.rooted_date_cell
        cell.props.editable = True
        self.view.connect(cell, 'edited', self.on_rooted_cell_edited, 'date')
        self.view.widgets.rooted_date_column.\
            set_cell_data_func(cell, _rooted_data_func, 'date')

        cell = self.view.widgets.rooted_quantity_cell
        cell.props.editable = True
        self.view.connect(cell, 'edited', self.on_rooted_cell_edited,
                          'quantity')
        self.view.widgets.rooted_quantity_column.\
            set_cell_data_func(cell, _rooted_data_func, 'quantity')


        self.view.connect('rooted_add_button', "clicked",
                          self.on_rooted_add_clicked)
        self.view.connect('rooted_remove_button', "clicked",
                          self.on_rooted_remove_clicked)


    def on_rooted_cell_edited(self, cell, path, new_text, prop):
        treemodel = self.view.widgets.rooted_treeview.get_model()
        rooted = treemodel[path][0]
        if getattr(rooted, prop) == new_text:
            return  # didn't change
        setattr(rooted, prop, utils.utf8(new_text))
        self.__dirty = True
        self.parent_ref().refresh_sensitivity()


    def on_rooted_add_clicked(self, button, *args):
        """
        """
        tree = self.view.widgets.rooted_treeview
        model = tree.get_model()
        rooted = PropRooted()
        rooted.cutting = self.model
        rooted.date = utils.today_str()
        treeiter = model.insert(0, [rooted])
        path = model.get_path(treeiter)
        column = tree.get_column(1)
        tree.set_cursor(path, column, start_editing=True)


    def on_rooted_remove_clicked(self, button, *args):
        """
        """
        tree = self.view.widgets.rooted_treeview
        model, treeiter = tree.get_selection().get_selected()
        if not treeiter:
            return
        rooted = model[treeiter][0]
        rooted.cutting = None
        model.remove(treeiter)
        self.__dirty = True
        self.parent_ref().refresh_sensitivity()


    def refresh_view(self):
        for widget, attr in self.widget_to_field_map.iteritems():
            value = getattr(self.model, attr)
            self.view.set_widget_value(widget, value)



class SeedPresenter(editor.GenericEditorPresenter):

    widget_to_field_map = {'seed_pretreatment_textview': 'pretreatment',
                           'seed_nseeds_entry': 'nseeds',
                           'seed_sown_entry': 'date_sown',
                           'seed_container_comboentry': 'container',
                           'seed_media_comboentry': 'compost',
                           'seed_location_comboentry': 'location',
                           'seed_mvdfrom_entry': 'moved_from',
                           'seed_mvdto_entry': 'moved_to',
                           'seed_germdate_entry': 'germ_date',
                           'seed_ngerm_entry': 'nseedling',
                           'seed_pctgerm_entry': 'germ_pct',
                           'seed_date_planted_entry': 'date_planted'}


    def __init__(self, parent, model, view, session):
        '''
        @param model: an instance of class Propagation
        @param view: an instance of PropagationEditorView
        '''
        super(SeedPresenter, self).__init__(model, view)
        self.parent_ref = weakref.ref(parent)
        self.session = session

        self.propagation = self.model
        self.propagation._seed = PropSeed()
        self.model = self.model._seed

        self.refresh_view()

        self.assign_simple_handler('seed_pretreatment_textview','pretreatment',
                                   editor.UnicodeOrNoneValidator())
        self.assign_simple_handler('seed_nseeds_entry', 'nseeds')
        self.assign_simple_handler('seed_sown_entry', 'date_sown')
        self.assign_simple_handler('seed_container_comboentry', 'container',
                                   editor.UnicodeOrNoneValidator())
        self.assign_simple_handler('seed_media_comboentry', 'compost',
                                   editor.UnicodeOrNoneValidator())
        self.assign_simple_handler('seed_location_comboentry', 'location',
                                   editor.UnicodeOrNoneValidator())
        self.assign_simple_handler('seed_mvdfrom_entry', 'moved_from',
                                   editor.UnicodeOrNoneValidator())
        self.assign_simple_handler('seed_mvdto_entry', 'moved_to',
                                   editor.UnicodeOrNoneValidator())
        self.assign_simple_handler('seed_germdate_entry', 'germ_date')
        self.assign_simple_handler('seed_ngerm_entry', 'nseedling')
        self.assign_simple_handler('seed_pctgerm_entry', 'germ_pct')
        self.assign_simple_handler('seed_date_planted_entry', 'date_planted')


    def refresh_view(self):
        for widget, attr in self.widget_to_field_map.iteritems():
            value = getattr(self.model, attr)
            self.view.set_widget_value(widget, value)


class PropagationEditorPresenter(editor.GenericEditorPresenter):

    widget_to_field_map = {'prop_type_combo': 'prop_type',
                           'prop_date_entry': 'date'}

    def __init__(self, model, view):
        '''
        @param model: an instance of class Propagation
        @param view: an instance of PropagationEditorView
        '''
        super(PropagationEditorPresenter, self).__init__(model, view)
        self.session = object_session(model)

        # initialize the propagation type combo and set the initial value
        self.init_translatable_combo('prop_type_combo', prop_type_values)
        self.view.connect('prop_type_combo', 'changed',
                          self.on_prop_type_changed)
        if self.model.prop_type:
            self.view.set_widget_value('prop_type_combo', self.model.prop_type)

        # don't allow changing the propagation type if we are editing
        # an existing propagation
        if model not in self.session.new or self.model.prop_type:
            self.view.widgets.prop_type_box.props.visible = False
        elif not self.model.prop_type:
            self.view.widgets.prop_type_box.props.visible = True
            self.view.widgets.prop_box_parent.props.visible = False

        self._cutting_presenter = CuttingPresenter(self, self.model, self.view,
                                                   self.session)
        self._seed_presenter = SeedPresenter(self, self.model, self.view,
                                                   self.session)

        self.assign_simple_handler('prop_date_entry', 'date')
        if not self.model.date:
            # set it to empty first b/c if we set the date and its the
            # same as the date string already in the entry then it
            # won't fire the 'changed' signal
            self.view.set_widget_value(self.view.widgets.prop_date_entry, '')
            self.view.set_widget_value(self.view.widgets.prop_date_entry,
                                       utils.today_str())


    def on_prop_type_changed(self, combo, *args):
        it = combo.get_active_iter()
        prop_type = combo.get_model()[it][0]
        self.set_model_attr('prop_type', prop_type)

        prop_box_map = {u'Seed': self.view.widgets.seed_box,
                        u'UnrootedCutting': self.view.widgets.cutting_box,
                        u'Other': self.view.widgets.prop_notes_box}

        parent = self.view.widgets.prop_box_parent
        prop_box = prop_box_map[prop_type]
        child = parent.get_child()
        if child:
            parent.remove(child)
        self.view.widgets.remove_parent(prop_box)
        parent.add(prop_box)
        self.view.widgets.prop_box_parent.props.visible = True


    def dirty(self):
        pass


    def set_model_attr(self, field, value, validator=None):
        """
        Set attributes on the model and update the GUI as expected.
        """
        #debug('set_model_attr(%s, %s)' % (field, value))
        super(PropagationEditorPresenter, self).set_model_attr(field, value,
                                                               validator)

    def refresh_sensitivity(self):
        pass

    def refresh_view(self):
        pass

    def start(self):
        r = self.view.start()
        return r


class PropagationEditor(editor.GenericModelViewPresenterEditor):

    # these have to correspond to the response values in the view
    RESPONSE_OK_AND_ADD = 11
    RESPONSE_NEXT = 22
    ok_responses = (RESPONSE_OK_AND_ADD, RESPONSE_NEXT)


    def __init__(self, model=None, parent=None):
        '''
        @param model: Propagation instance or None
        @param parent: the parent widget
        '''
        # the view and presenter are created in self.start()
        self.view = None
        self.presenter = None
        if model is None:
            model = Propagation()
        super(PropagationEditor, self).__init__(model, parent)
        if not parent and bauble.gui:
            parent = bauble.gui.window
        self.parent = parent

        view = PropagationEditorView(parent=self.parent)
        self.presenter = PropagationEditorPresenter(self.model, view)

        # add quick response keys
        self.attach_response(view.get_window(), gtk.RESPONSE_OK, 'Return',
                             gtk.gdk.CONTROL_MASK)
        self.attach_response(view.get_window(), self.RESPONSE_OK_AND_ADD, 'k',
                             gtk.gdk.CONTROL_MASK)
        self.attach_response(view.get_window(), self.RESPONSE_NEXT, 'n',
                             gtk.gdk.CONTROL_MASK)

        # set the default focus
        # if self.model.species is None:
        #     view.widgets.acc_species_entry.grab_focus()
        # else:
        #     view.widgets.acc_code_entry.grab_focus()


    def handle_response(self, response, commit=True):
        '''
        handle the response from self.presenter.start() in self.start()
        '''
        not_ok_msg = 'Are you sure you want to lose your changes?'
        if response == gtk.RESPONSE_OK or response in self.ok_responses:
            try:
                #debug(self.model)
                #debug(self.model.details)
                if self.model.prop_type == u'UnrootedCutting':
                    utils.delete_or_expunge(self.model._seed)
                    #self.session.expunge(self.model._seed)
                    self.model._seed = None
                    del self.model._seed
                elif self.model.prop_type == u'Seed':
                    utils.delete_or_expunge(self.model._cutting)
                    #self.session.expunge(self.model._cutting)
                    self.model._cutting = None
                    del self.model._cutting

                if self.presenter.dirty() and commit:
                    self.commit_changes()
            except SQLError, e:
                msg = _('Error committing changes.\n\n%s') % \
                      utils.xml_safe_utf8(unicode(e.orig))
                utils.message_details_dialog(msg, str(e), gtk.MESSAGE_ERROR)
                self.session.rollback()
                return False
            except Exception, e:
                msg = _('Unknown error when committing changes. See the '\
                        'details for more information.\n\n%s') \
                        % utils.xml_safe_utf8(e)
                debug(traceback.format_exc())
                utils.message_details_dialog(msg, traceback.format_exc(),
                                             gtk.MESSAGE_ERROR)
                self.session.rollback()
                return False
        elif self.presenter.dirty() and utils.yes_no_dialog(not_ok_msg) \
                 or not self.presenter.dirty():
            self.session.rollback()
            return True
        else:
            return False

        return True


    def start(self, commit=True):
        while True:
            response = self.presenter.start()
            self.presenter.view.save_state()
            if self.handle_response(response, commit):
                break

        self.session.close() # cleanup session
        self.presenter.cleanup()
        return self.model






