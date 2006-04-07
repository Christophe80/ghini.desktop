#
# accessions module
#


import gtk
from sqlobject import * 
import bauble.utils as utils
from bauble.plugins import BaubleTable, tables, editors
from bauble.plugins.editor import TreeViewEditorDialog, TableEditorDialog
from bauble.utils.log import debug


class Accession(BaubleTable):

    class sqlmeta(BaubleTable.sqlmeta):
	defaultOrder = 'acc_id'

    values = {} # dictionary of values to restrict to columns
    acc_id = StringCol(length=20, notNull=True, alternateID=True)
    
    
    prov_type = EnumCol(enumValues=("Wild", # Wild,
                                    "Propagule of cultivated wild plant", # Propagule of wild plant in cultivation
                                    "Not of wild source", # Not of wild source
                                    "Insufficient Data", # Insufficient data
                                    "Unknown",
                                    "<not set>"),
                        default = "<not set>")

    # wild provenance status, wild native, wild non-native, cultivated native
    wild_prov_status = EnumCol(enumValues=("Wild native", # Endemic found within it indigineous range
                                           "Wild non-native", # Propagule of wild plant in cultivation
                                           "Cultivated native", # Not of wild source
                                           "Insufficient Data", # Insufficient data
                                           "Unknown",
                                           "<not set>"),
                               default="<not set>")
    
    # propagation history ???
    #prop_history = StringCol(length=11, default=None)

    # accession lineage, parent garden code and acc id ???
    #acc_lineage = StringCol(length=50, default=None)    
    #acctxt = StringCol(default=None) # ???
    
    #
    # verification, a verification table would probably be better and then
    # the accession could have a verification history with a previous
    # verification id which could create a chain for the history
    #
    #ver_level = StringCol(length=2, default=None) # verification level
    #ver_name = StringCol(length=50, default=None) # verifier's name
    #ver_date = DateTimeCol(default=None) # verification date
    #ver_hist = StringCol(default=None)  # verification history
    #ver_lit = StringCol(default=None) # verification lit
    #ver_id = IntCol(default=None) # ?? # verifier's ID??
    

    # i don't think this is the red list status but rather the status
    # of this accession in some sort of conservation program
    #consv_status = StringCol(default=None) # conservation status, free text
    
    # foreign keys and joins
    species = ForeignKey('Species', notNull=True, cascade=False)
    plants = MultipleJoin("Plant", joinColumn='accession_id')
    
    # these should probably be hidden then we can do some trickery
    # in the accession editor to choose where a collection or donation
    # source, the source will contain one of collection or donation
    # tables
    # 
    # holds the string 'Collection' or 'Donation' which indicates where
    # we should get the source information from either of those columns
    source_type = StringCol(length=64, default=None)    
                            
    # the source type says whether we should be looking at the 
    # _collection or _donation joins for the source info
    #_collection = SingleJoin('Collection', joinColumn='accession_id', makeDefault=None)
    _collection = SingleJoin('Collection', joinColumn='accession_id')
    _donation = SingleJoin('Donation', joinColumn='accession_id', makeDefault=None)
        
    notes = UnicodeCol(default=None)
    
    # these probably belong in separate tables with a single join
    #cultv_info = StringCol(default=None)      # cultivation information
    #prop_info = StringCol(default=None)       # propogation information
    #acc_uses = StringCol(default=None)        # accessions uses, why diff than taxon uses?
    
    def __str__(self): 
        return self.acc_id
    
    def markup(self):
        return '%s (%s)' % (self.acc_id, self.species.markup())


#
# Accession editor
#

def get_source(row):
    if row.source_type == None:
        return None
    elif row.source_type == tables['Donation'].__name__:
        # the __name__ should be 'Donation'
        return row._donation
    elif row.source_type == tables['Collection'].__name__:
        return row._collection
    else:
        raise ValueError('unknown source type: ' + str(row.source_type))
    

    
# Model View Presenter patter
# see http://www.martinfowler.com/eaaDev/ModelViewPresenter.html
class AccessionPresenter:
    
    def __init__(self, model, view):
        # put the data from the model into the view
        pass

class new_AccessionEditor(TableEditorDialog):

    label = 'Accessions'

    def __init__(self, parent=None, select=None, defaults={}):	
    	path = os.path.join(paths.lib_dir(), "plugins", "garden")
    	self.glade_xml = gtk.glade.XML(path + os.sep + 'editors.glade')
    	dialog = self.glade_xml.get_widget('acc_editor_dialog')
    	TableEditorDialog.__init__(self, Accession, title='Accessions Editor',
                                   parent=parent, select=select, 
                                   defaults=defaults, dialog=dialog)
	

    def completion_match_func(self, completion, key_string, iter, data=None):        
        species = completion.get_model().get_value(iter, 0)        
        if str(species).lower().startswith(key_string.lower()):
            return True
        return False
        
        
    def species_cell_data_func(self, column, renderer, model, iter, data=None):
        species = model.get_value(iter, 0)        
        renderer.set_property('markup', str(species))     
        
    
    def start_gui(self):
    	self.name_entry = self.glade_xml.get_widget('name_entry')
    	completion = gtk.EntryCompletion()	
        r = gtk.CellRendererText()
        completion.pack_start(r)
        completion.set_cell_data_func(r, self.species_cell_data_func)
        completion.set_match_func(self.completion_match_func)
    	completion.set_minimum_key_length(3)
    	completion.set_inline_completion(True)
    	completion.set_popup_completion(True)         
    	self.name_entry.set_completion(completion)
    	self.name_entry.connect('insert-at-cursor', self.on_insert_at_cursor)
    	self.name_entry.connect('insert-text', self.on_insert_text)

        
    def _set_names_completions(self, text):
    	parts = text.split(" ")
    	genus = parts[0]
    	sr = tables["Genus"].select("genus LIKE '"+genus+"%'")
        model = gtk.ListStore(object)     
    	for row in sr:
            for species in row.species:
                model.append([species,])
    			    
    	completion = self.name_entry.get_completion()
    	completion.set_model(model)
    	completion.connect('match-selected', self.on_match_selected)


    def on_match_selected(self, completion, model, iter, data=None):    
        species = model.get_value(iter, 0)
        completion.get_entry().set_text(str(species))


    def on_insert_text(self, entry, new_text, new_text_length, position):
    	# TODO: this is flawed since we can't get the index into the entry
    	# where the text is being inserted so if the used inserts text into 
    	# the middle of the string then this could break
    	entry_text = entry.get_text()
    	cursor = entry.get_position()
    	full_text = entry_text[:cursor] + new_text + entry_text[cursor:]    
    	# this funny logic is so that completions are reset if the user
    	# paste multiple characters in the entry
    	if len(new_text) == 1 and len(full_text) == 2:
    	    self._set_names_completions(full_text)
    	elif new_text_length > 2:
    	    self._set_names_completions(full_text)
	
    def on_expand_source(self, *args):
        pass
    
    
    def start(self):	
    	self.start_gui()
    	self._run()
	
        
    
class AccessionEditor(TreeViewEditorDialog):

    visible_columns_pref = "editor.accession.columns"
    column_width_pref = "editor.accession.column_width"
    default_visible_list = ['acc_id', 'species']

    label = 'Accessions'

    def __init__(self, parent=None, select=None, defaults={}):
        
        TreeViewEditorDialog.__init__(self, Accession, "Accession Editor", 
                                      parent, select=select, defaults=defaults)
        titles = {"acc_id": "Acc ID",
                   "speciesID": "Name",
                   "prov_type": "Provenance Type",
                   "wild_prov_status": "Wild Provenance Status",
                   'source_type': 'Source',
                   'notes': 'Notes'
#                   "ver_level": "Verification Level",           
#                   "ver_name": "Verifier's Name",
#                   "ver_date": "Verification Date",
#                   "ver_lit": "Verification Literature",
                   }

        self.columns.titles = titles
        self.columns['source_type'].meta.editor = editors["SourceEditor"]
        self.columns['source_type'].meta.getter = get_source
        
        self.columns['speciesID'].meta.get_completions = \
            self.get_species_completions
        
        # set the accession column of the table that will be in the 
        # source_type columns returned from self.get_values_from view
        # TODO: this is a little hoaky and could use some work, might be able
        # to do this automatically if the value in the column is a table
        # the the expected type is a single join
        # could do these similar to the way we handle joins in 
        # create_view_columns
        #self.table_meta.foreign_keys = [('_collection', 'accession'),
        #                                ('_donation', 'accession')]
        
        
    def get_species_completions(self, text):
        # get entry and determine from what has been input which
        # field is currently being edited and give completion
        # if this return None then the entry will never search for completions
        # TODO: finish this, it would be good if we could just stick
        # the table row in the model and tell the renderer how to get the
        # string to match on, though maybe not as fast, and then to get
        # the value we would only have to do a row.id instead of storing
        # these tuples in the model
        # UPDATE: the only problem with sticking the table row in the column
        # is how many queries would it take to screw in a lightbulb, this
        # would be easy to test it just needs to be done
        # TODO: there should be a better/faster way to do this 
        # using a join or something
        parts = text.split(" ")
        genus = parts[0]
        sr = tables["Genus"].select("genus LIKE '"+genus+"%'")
        model = gtk.ListStore(str, object) 
        for row in sr:
            for species in row.species:                
                model.append((str(species), species))
        return model
    
        
    def _model_row_to_values(self, row):
	'''
	_model_row_to_values
	row: iter from self.model
	return None if you don't want to commit anything
	'''    
	values = super(AccessionEditor, self)._model_row_to_values(row)
	if values is None:
	    return None
        if 'source_type' in values and values['source_type'] is not None:
            source_class = values['source_type'].__class__.__name__
            attribute_name = '_' + source_class.lower()
            self.columns.joins.append(attribute_name)                
            values[attribute_name] = values.pop('source_type')
            values['source_type'] = source_class
        return values
    

#
# TODO: fix this so it asks if you want to adds plant when you're done
#
#
#    def commit_changes_old(self, commit_transaction=True):
#        committed_rows = TreeViewEditorDialog.commit_changes(self, 
#                                                            commit_transaction)
#        if not committed_rows:
#            return committed_rows
#                            
#        # TODO: here should we iterate over the response from 
#        # TreeViewEditorDialog.commit_changes or is the 'values' sufficient
#        for row in committed_rows:
#            pass
#            #debug(row)
#        return committed_rows
#    
#        #
#        # it would be nice to have this done later
#        #
#        for v in self.values:
#            acc_id = v["acc_id"]
#            sel = tables["Accession"].selectBy(acc_id=acc_id)
#            if sel.count() > 1:
#                raise Exception("AccessionEditor.commit_changes():  "\
#                                "more than one accession exists with id: " +
#                                acc_id)
#            msg  = "No Plants/Clones exist for this accession %s. Would you "\
#                   "like to add them now?"
#            if not utils.yes_no_dialog(msg % acc_id):
#                continue
#            e = editors['PlantEditor'](defaults={"accessionID":sel[0]},
#                                       connection=self._old_connection)
#            response = e.start()
#            #if response == gtk.RESPONSE_OK or response == gtk.RESPONSE_ACCEPT:
#            #    e.commit_changes()
#            #e.destroy()
#        return committed_rows
        
#
# infobox for searchview
#
try:
    import os
    import bauble.paths as paths
    from bauble.plugins.searchview.infobox import InfoBox, InfoExpander, \
        set_widget_value        
except ImportError:
    pass
else:
    class GeneralAccessionExpander(InfoExpander):
        """
        generic information about an accession like
        number of clones, provenance type, wild provenance type, speciess
        """
    
        def __init__(self, glade_xml):
            InfoExpander.__init__(self, "General", glade_xml)
            general_window = self.glade_xml.get_widget('general_window')
            w = self.glade_xml.get_widget('general_box')
            general_window.remove(w)
            self.vbox.pack_start(w)
        
        
        def update(self, row):
            set_widget_value(self.glade_xml, 'name_data', 
			     row.species.markup(True))
            set_widget_value(self.glade_xml, 'nplants_data', len(row.plants))
            set_widget_value(self.glade_xml, 'prov_data',row.prov_type, False)
            
            
    class NotesExpander(InfoExpander):
        """
        the accession's notes
        """
    
        def __init__(self, glade_xml):
            InfoExpander.__init__(self, "Notes", glade_xml)
            notes_window = self.glade_xml.get_widget('notes_window')
            w = self.glade_xml.get_widget('notes_box')
            notes_window.remove(w)
            self.vbox.pack_start(w)
        
        
        def update(self, row):
            set_widget_value(self.glade_xml, 'notes_data', row.notes)            
    
    
    class SourceExpander(InfoExpander):
        
        def __init__(self, glade_xml):
            InfoExpander.__init__(self, 'Source', glade_xml)
            self.curr_box = None
        
        
        def update_collections(self, collection):
            
            set_widget_value(self.glade_xml, 'loc_data', collection.locale)
            
            geo_accy = collection.geo_accy
            if geo_accy is None:
                geo_accy = ''
            else: geo_accy = '(+/-)' + geo_accy + 'm.'
            
            if collection.latitude is not None:
                set_widget_value(self.glade_xml, 'lat_data',
                                 '%.2f %s' %(collection.latitude, geo_accy))
            if collection.longitude is not None:
                set_widget_value(self.glade_xml, 'lon_data',
                                '%.2f %s' %(collection.longitude, geo_accy))                                
            
            v = collection.elevation
            if collection.elevation_accy is not None:
                v = '+/- ' + v + 'm.'
            set_widget_value(self.glade_xml, 'elev_data', v)
            
            set_widget_value(self.glade_xml, 'coll_data', collection.collector)
            set_widget_value(self.glade_xml, 'date_data', collection.coll_date)
            #set_widget_value(self.glade_xml,'date_data', collection.coll_date)
            set_widget_value(self.glade_xml, 'collid_data', collection.coll_id)
            set_widget_value(self.glade_xml,'habitat_data', collection.habitat)
            set_widget_value(self.glade_xml,'collnotes_data', collection.notes)
            
                
        def update_donations(self, donation):
            set_widget_value(self.glade_xml, 'donor_data', 
                             tables['Donor'].get(donation.donorID).name)
            set_widget_value(self.glade_xml, 'donid_data', donation.donor_acc)
            set_widget_value(self.glade_xml, 'donnotes_data', donation.notes)
        
        
        def update(self, value):        
            if self.curr_box is not None:
                self.vbox.remove(self.curr_box)
                    
            #assert value is not None
            if value is None:
                return
            
            if isinstance(value, tables["Collection"]):
                coll_window = self.glade_xml.get_widget('collections_window')
                w = self.glade_xml.get_widget('collections_box')
                coll_window.remove(w)
                self.curr_box = w
                self.update_collections(value)        
            elif isinstance(value, tables["Donation"]):
                don_window = self.glade_xml.get_widget('donations_window')
                w = self.glade_xml.get_widget('donations_box')
                don_window.remove(w)
                self.curr_box = w
                self.update_donations(value)            
            else:
                msg = "Unknown type for source: " + str(type(value))
                utils.message_dialog(msg, gtk.MESSAGE_ERROR)
            
            #if self.curr_box is not None:
            self.vbox.pack_start(self.curr_box)
            #self.set_expanded(False) # i think the infobox overrides this
            #self.set_sensitive(False)
            
    
    class AccessionInfoBox(InfoBox):
        """
        - general info
        - source
        """
        def __init__(self):
            InfoBox.__init__(self)
            path = os.path.join(paths.lib_dir(), "plugins", "garden")
            self.glade_xml = gtk.glade.XML(path + os.sep + "acc_infobox.glade")
            
            self.general = GeneralAccessionExpander(self.glade_xml)
            self.add_expander(self.general)
            
            self.source = SourceExpander(self.glade_xml)
            self.add_expander(self.source)
            
            self.notes = NotesExpander(self.glade_xml)
            self.add_expander(self.notes)
    
    
        def update(self, row):        
            self.general.update(row)
            
            if row.notes is None:
                self.notes.set_expanded(False)
                self.notes.set_sensitive(False)
            else:
                self.notes.set_expanded(True)
                self.notes.set_sensitive(True)
                self.notes.update(row)
            
            # TODO: should test if the source should be expanded from the prefs
            if row.source_type == None:
                self.source.set_expanded(False)
                self.source.set_sensitive(False)
            elif row.source_type == 'Collection':
                self.source.set_expanded(True)
                self.source.update(row._collection)
            elif row.source_type == 'Donation':
                self.source.set_expanded(True)
                self.source.update(row._donation)
