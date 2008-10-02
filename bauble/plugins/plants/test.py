# -*- coding: utf-8 -*-
#
# test.py
#
# Description: test for the Plant plugin
#

import os, sys, unittest
from sqlalchemy import *
from sqlalchemy.exc import *
from sqlalchemy.orm.exc import *
import bauble
import bauble.utils as utils
from bauble.plugins.plants.species_model import Species, VernacularName, \
     SpeciesSynonym, DefaultVernacularName
from bauble.plugins.plants.family import *
from bauble.plugins.plants.genus import *
from bauble.plugins.plants.geography import *
from bauble.test import BaubleTestCase

#
# TODO: things to create tests for
#
# - test schema cascading works for all tables in the plants module
# - test unicode is working properly in the relevant fields, especially
# in the Species.str function
# - test the setting the default vernacular name on a species is working
# and that delete vernacular names and default vernacular names does
# proper  cascading
# make sure that deleting either of the species referred to in a synonym
# deletes the synonym

# TODO: create more species name test cases
# TODO: create some scenarios that should fail

family_test_data = ({'id': 1, 'family': 'Orchidaceae'},
                    {'id': 2, 'family': 'Leguminosae'},
                    {'id': 3, 'family': 'Polypodiaceae'})

genus_test_data = ({'id': 1, 'genus': 'Maxillaria', 'family_id': 1},
                   {'id': 2, 'genus': 'Encyclia', 'family_id': 1},
                   {'id': 3, 'genus': 'Abrus', 'family_id': 2},
                   {'id': 4, 'genus': 'Campyloneurum', 'family_id': 3},
                   )

species_test_data = ({'id': 1, 'sp': u'variabilis', 'genus_id': 1,
                      'sp_author': u'Bateman ex Lindl.'},
                     {'id': 2, 'sp': u'cochleata', 'genus_id': 2,
                      'sp_author': u'(L.) Lem\xe9e'},
                     {'id': 3, 'sp': u'precatorius', 'genus_id': 3,
                      'sp_author': u'L.'},
                     {'id': 4, 'sp': u'alapense', 'genus_id': 4,
                      'sp_hybrid': u'x', 'sp_author': u'F\xe9e'},
                     {'id': 5, 'sp': u'cochleata', 'genus_id': 2,
                      'sp_author': u'(L.) Lem\xe9e', 'infrasp_rank': u'var.',
                      'infrasp': u'cochleata'},
                     {'id': 6, 'sp': u'cochleata', 'genus_id': 2,
                      'sp_author': u'(L.) Lem\xe9e', 'infrasp_rank': u'cv.',
                      'infrasp': u'Black Night'},
                     {'id': 7, 'sp': u'precatorius', 'genus_id': 3,
                      'sp_author': u'L.', 'cv_group': u'SomethingRidiculous'},
                     {'id': 8, 'sp': u'precatorius', 'genus_id': 3,
                      'sp_author': u'L.', 'infrasp_rank': u'cv.',
                      'infrasp': u'Hot Rio Nights',
                      'cv_group': u'SomethingRidiculous'},
                     {'id': 9, 'sp': u'generalis', 'genus_id': 1,
                      'sp_hybrid': u'x', 'infrasp_rank': u'cv.',
                      'infrasp': u'Red'},
                     {'id': 10, 'sp': u'generalis', 'genus_id': 1,
                      'sp_hybrid': u'x', 'sp_author': u'L.',
                      'infrasp_rank': u'cv.', 'infrasp': u'Red',
                      'cv_group': u'SomeGroup'},
                     )

species_str_map = {\
    1: 'Maxillaria variabilis',
    2: 'Encyclia cochleata',
    3: 'Abrus precatorius',
    4: 'Campyloneurum x alapense',
    5: 'Encyclia cochleata var. cochleata',
    6: "Encyclia cochleata 'Black Night'",
    7: 'Abrus precatorius SomethingRidiculous Group',
    8: "Abrus precatorius (SomethingRidiculous Group) 'Hot Rio Nights'",
    9: "Maxillaria x generalis 'Red'",
    10:"Maxillaria x generalis (SomeGroup Group) 'Red'"
    }

species_markup_map = {\
    1: '<i>Maxillaria</i> <i>variabilis</i>',
    2: '<i>Encyclia</i> <i>cochleata</i>',
    3: '<i>Abrus</i> <i>precatorius</i>',
    4: '<i>Campyloneurum</i> x <i>alapense</i>',
    5: '<i>Encyclia</i> <i>cochleata</i> var. <i>cochleata</i>',
    6: '<i>Encyclia</i> <i>cochleata</i> \'Black Night\''}

species_str_authors_map = {\
    1: 'Maxillaria variabilis Bateman ex Lindl.',
    2: u'Encyclia cochleata (L.) Lem\xe9e',
    3: 'Abrus precatorius L.',
    4: u'Campyloneurum x alapense F\xe9e',
    5: u'Encyclia cochleata (L.) Lem\xe9e var. cochleata',
    6: u'Encyclia cochleata (L.) Lem\xe9e \'Black Night\''}

species_markup_authors_map = {\
    1: '<i>Maxillaria</i> <i>variabilis</i> Bateman ex Lindl.',
    2: u'<i>Encyclia</i> <i>cochleata</i> (L.) Lem\xe9e',
    3: '<i>Abrus</i> <i>precatorius</i> L.',
    4: u'<i>Campyloneurum</i> x <i>alapense</i> F\xe9e',
    5: u'<i>Encyclia</i> <i>cochleata</i> (L.) Lem\xe9e var. <i>cochleata</i>',
    6: u'<i>Encyclia</i> <i>cochleata</i> (L.) Lem\xe9e \'Black Night\''}

sp_synonym_test_data = ({'id': 1, 'synonym_id': 1, 'species_id': 2},
                        )

vn_test_data = ({'id': 1, 'name': u'SomeName', 'language': u'English',
                 'species_id': 1},
                {'id': 2, 'name': u'SomeName 2', 'language': u'English',
                 'species_id': 1},
                )

test_data_table_control = ((Family, family_test_data),
                           (Genus, genus_test_data),
                           (Species, species_test_data),
                           (VernacularName, vn_test_data),
                           (SpeciesSynonym, sp_synonym_test_data))

def setUp_test_data():
    '''
    if this method is called again before tearDown_test_data is called you
    will get an error about the test data rows already existing in the database
    '''
    for mapper, data in test_data_table_control:
        table = mapper.__table__
        for row in data:
            table.insert().execute(row)
        for col in table.c:
            utils.reset_sequence(col)


def tearDown_test_data():
    for mapper, data in test_data_table_control:
        table = mapper.__table__
        for row in data:
            #print 'delete %s %s' % (table, row['id'])
            table.delete(table.c.id==row['id']).execute()



class PlantTestCase(BaubleTestCase):

    def __init__(self, *args):
        super(PlantTestCase, self).__init__(*args)


    def setUp(self):
        super(PlantTestCase, self).setUp()
        setUp_test_data()


    def tearDown(self):
        super(PlantTestCase, self).tearDown()
        tearDown_test_data()


class FamilyTests(PlantTestCase):
    """
    Test for Family and FamilySynonym
    """
    def test_cascades(self):
        """
        Test that cascading is set up properly
        """
        family = Family(family=u'family')
        genus = Genus(family=family, genus=u'genus')
        self.session.add_all([family, genus])
        self.session.commit()

        # test that deleting a family deletes an orphaned genus
        self.session.delete(family)
        query = self.session.query(Genus).filter_by(family_id=family.id)
        self.assertRaises(NoResultFound, query.one)


    def test_synonyms(self):
        """
        Test that Family.synonyms works correctly
        """
        family = Family(family=u'family')
        family2 = Family(family=u'family2')
        family.synonyms.append(family2)
        self.session.add_all([family, family2])
        self.session.commit()

        # test that family2 was added as a synonym to family
        family = self.session.query(Family).filter_by(family=u'family').one()
        self.assert_(family2 in family.synonyms)

        # test that the synonyms relation and family backref works
        self.assert_(family._synonyms[0].family == family)
        self.assert_(family._synonyms[0].synonym == family2)

        # test that the synonyms are removed properly
        family.synonyms.remove(family2)
        self.session.commit()
        self.assert_(family2 not in family.synonyms)

        # test synonyms contraints, e.g that a family cannot have the
        # same synonym twice
        family.synonyms.append(family2)
        self.session.commit()
        family.synonyms.append(family2)
        self.assertRaises(IntegrityError, self.session.commit)
        self.session.rollback()

        # test that clearing all the synonyms works
        family.synonyms.clear()
        self.session.commit()
        self.assert_(len(family.synonyms) == 0)
        self.assert_(self.session.query(FamilySynonym).count() == 0)

        # test that deleting a family that is a synonym of another family
        # deletes all the dangling object s
        family.synonyms.append(family2)
        self.session.commit()
        self.session.delete(family2)
        self.assert_(self.session.query(FamilySynonym).count() == 0)

        # test that deleting the previous synonyms didn't delete the
        # family that it refered to
        self.assert_(self.session.query(Family).get(family.id))

        # test that deleting a family that has synonyms deletes all
        # the synonyms that refer to that family deletes all the
        family.synonyms.append(family2)
        self.session.commit()
        self.session.delete(family)
        self.assert_(self.session.query(FamilySynonym).count() == 0)


    def test_constraints(self):
        """
        Test that the family constraints were created correctly
        """
        values = [dict(family=u'family'),
                  dict(family=u'family', qualifier=u's. lat.')]
        for v in values:
            self.session.add(Family(**v))
            self.session.add(Family(**v))
            self.assertRaises(IntegrityError, self.session.commit)
            self.session.rollback()

        # test that family cannot be null
        self.session.add(Family(family=None))
        self.assertRaises(IntegrityError, self.session.commit)
        self.session.rollback()


    def test_str(self):
        """
        Test that the family str function works as expected
        """
        f = Family()
        self.assert_(str(f) == repr(f))
        f = Family(family=u'fam')
        self.assert_(str(f) == 'fam')
        f.qualifier = 's. lat.'
        self.assert_(str(f) == 'fam s. lat.')



class GenusTests(PlantTestCase):

    def test_synonyms(self):
        family = Family(family=u'family')
        genus = Genus(family=family, genus=u'genus')
        genus2 = Genus(family=family, genus=u'genus2')
        genus.synonyms.append(genus2)
        self.session.add_all([genus, genus2])
        self.session.commit()

        # test that genus2 was added as a synonym to genus
        genus = self.session.query(Genus).filter_by(genus=u'genus').one()
        self.assert_(genus2 in genus.synonyms)

        # test that the synonyms relation and genus backref works
        self.assert_(genus._synonyms[0].genus == genus)
        self.assert_(genus._synonyms[0].synonym == genus2)

        # test that the synonyms are removed properly
        genus.synonyms.remove(genus2)
        self.session.commit()
        self.assert_(genus2 not in genus.synonyms)

        # test synonyms contraints, e.g that a genus cannot have the
        # same synonym twice
        genus.synonyms.append(genus2)
        self.session.commit()
        genus.synonyms.append(genus2)
        self.assertRaises(IntegrityError, self.session.commit)
        self.session.rollback()

        # test that clearing all the synonyms works
        genus.synonyms.clear()
        self.session.commit()
        self.assert_(len(genus.synonyms) == 0)
        self.assert_(self.session.query(GenusSynonym).count() == 0)

        # test that deleting a genus that is a synonym of another genus
        # deletes all the dangling object s
        genus.synonyms.append(genus2)
        self.session.commit()
        self.session.delete(genus2)
        self.assert_(self.session.query(GenusSynonym).count() == 0)

        # test that deleting the previous synonyms didn't delete the
        # genus that it refered to
        self.assert_(self.session.query(Genus).get(genus.id))

        # test that deleting a genus that has synonyms deletes all
        # the synonyms that refer to that genus deletes all the
        genus.synonyms.append(genus2)
        self.session.commit()
        self.session.delete(genus)
        self.assert_(self.session.query(GenusSynonym).count() == 0)


    def test_contraints(self):
        """
        Test that the genus constraints were created correctly
        """
        family = Family(family=u'family')
        self.session.add(family)

        # if any of these values are inserted twice they should raise
        # an IntegrityError because the UniqueConstraint on Genus
        values = [dict(family=family, genus=u'genus'),
                  dict(family=family, genus=u'genus', author=u'author'),
                  dict(family=family, genus=u'genus', hybrid=u'x'),
                  dict(family=family, genus=u'genus', hybrid=u'x',
                       author=u'author')]
        for v in values:
            self.session.add(Genus(**v))
            self.session.add(Genus(**v))
            self.assertRaises(IntegrityError, self.session.commit)
            self.session.rollback()


    def test_str(self):
        """
        Test that the Genus string functions works as expected
        """
        pass


class SpeciesTests(PlantTestCase):


    def test_string(self):
        def get_sp_str(id, **kwargs):
            return Species.str(self.session.query(Species).get(id), **kwargs)

        for id, s in species_str_map.iteritems():
            spstr = get_sp_str(id)
            self.assert_(spstr == s,
                         '%s != %s ** %s' % (spstr, s, unicode(spstr)))

        for id, s in species_str_authors_map.iteritems():
            spstr = get_sp_str(id, authors=True)
            self.assert_(spstr == s,
                         '%s != %s ** %s' % (spstr, s, unicode(spstr)))

        for id, s in species_markup_map.iteritems():
            spstr = get_sp_str(id, markup=True)
            self.assert_(spstr == s,
                         '%s != %s ** %s' % (spstr, s, unicode(spstr)))

        for id, s in species_markup_authors_map.iteritems():
            spstr = get_sp_str(id, markup=True, authors=True)
            self.assert_(spstr == s,
                         '%s != %s ** %s' % (spstr, s, unicode(spstr)))


    def test_vernacular_name(self):
        """
        Test the vernacular_name property on Species
        """
        family = Family(family=u'family')
        genus = Genus(family=family, genus=u'genus')
        sp = Species(genus=genus, sp=u'sp')
        self.session.add_all([family, genus, sp])
        self.session.commit()

        # add a name
        vn = VernacularName(name=u'name')
        sp.vernacular_names.append(vn)
        self.session.commit()
        self.assert_(vn in sp.vernacular_names)

        # test that removing a name removes deleted orphaned objects
        sp.vernacular_names.remove(vn)
        self.session.commit()
        q = self.session.query(VernacularName).filter_by(species_id=sp.id)
        self.assertRaises(NoResultFound, q.one)


    def test_default_vernacular_name(self):
        """
        Test the default_vernacular_name property on Species
        """
        family = Family(family=u'family')
        genus = Genus(family=family, genus=u'genus')
        sp = Species(genus=genus, sp=u'sp')
        vn = VernacularName(name=u'name')
        sp.vernacular_names.append(vn)
        self.session.add_all([family, genus, sp, vn])
        self.session.commit()

        # test that if you set the default_vernacular_name on a
        # species then it automatically adds it to vernacular_names
        default = VernacularName(name=u'default')
        sp.default_vernacular_name = default
        self.session.commit()
        self.assert_(vn in sp.vernacular_names)

        # test that removing a vernacular name removes it from
        # default_vernacular_name, this test also effectively tests VNList
        dvid = sp._default_vernacular_name.id
        sp.vernacular_names.remove(default)
        self.session.commit()
        self.assertEquals(sp.default_vernacular_name, None)
        q = self.session.query(DefaultVernacularName)
        self.assertRaises(NoResultFound, q.filter_by(species_id=sp.id).one)
        self.assertRaises(NoResultFound, q.filter_by(id=dvid).one)

        # test that setting default_vernacular_name to None
        # removes the name properly and deletes any orphaned objects
        sp.vernacular_names.append(vn)
        sp.default_vernacular_name = vn
        self.session.commit()
        dvid = sp._default_vernacular_name.id
        sp.default_vernacular_name = None
        self.session.commit()
        q = self.session.query(DefaultVernacularName)
        self.assertRaises(NoResultFound, q.filter_by(species_id=sp.id).one)
        self.assertRaises(NoResultFound, q.filter_by(id=dvid).one)

        # test that calling __del__ on a default vernacular name removes it
        sp.default_vernacular_name = vn
        self.session.commit()
        dvid = sp._default_vernacular_name.id
        del sp.default_vernacular_name
        self.session.commit()
        self.assertEquals(sp.default_vernacular_name, None)
        q = self.session.query(DefaultVernacularName)
        self.assertRaises(NoResultFound, q.filter_by(species_id=sp.id).one)
        self.assertRaises(NoResultFound, q.filter_by(id=dvid).one)

        # test for regression in bug Launchpad #123286
        vn1 = VernacularName(name=u'vn1')
        vn2 = VernacularName(name=u'vn2')
        sp.default_vernacular_name = vn1
        sp.default_vernacular_name = vn2
        self.session.commit()


    def test_synonyms(self):
        """
        Test the synonyms property on Species
        """
        load_sp = lambda id: self.session.query(Species).get(id)

        def syn_str(id1, id2, isit='not'):
            sp1 = load_sp(id1)
            sp2 = load_sp(id2)
            return '%s(%s).synonyms: %s' % \
                   (sp1, sp1.id,
                    str(map(lambda s: '%s(%s)' % \
                            (s, s.id), sp1.synonyms)))

        def synonym_of(id1, id2):
            sp1 = load_sp(id1)
            sp2 = load_sp(id2)
            return sp2 in sp1.synonyms

        # test that appending a synonym works using species.synonyms
        sp1 = load_sp(1)
        sp2 = load_sp(2)
        sp1.synonyms.append(sp2)
        self.session.flush()
        self.assert_(synonym_of(1, 2), syn_str(1, 2))

        # test that removing a synonyms works using species.synonyms
        sp1.synonyms.remove(sp2)
        self.session.flush()
        self.failIf(synonym_of(1, 2), syn_str(1, 2))

        self.session.clear()

        # test that appending a synonym works using species._synonyms
        sp1 = load_sp(1)
        sp2 = load_sp(2)
        syn = SpeciesSynonym(sp2)
        sp1._synonyms.append(syn)
        self.session.flush()
        self.assert_(synonym_of(1, 2), syn_str(1, 2))

        # test that removing a synonyms works using species._synonyms
        sp1._synonyms.remove(syn)
        self.session.flush()
        self.failIf(synonym_of(1, 2), syn_str(1, 2))

        # TODO: need to test adding a species and then immediately remove it
        # TOOD: need to test removing a species and then immediately adding
        # the same species
        self.session.clear()
        sp1 = load_sp(1)
        sp2 = load_sp(2)
        sp1.synonyms.append(sp2)
        self.session.flush()

        sp1.synonyms.remove(sp2)
        for s in self.session.dirty:
            if isinstance(s, SpeciesSynonym) and s.synonym == sp2:
                self.session.flush([s])
        sp1.synonyms.append(sp2)
        self.session.flush()

        self.session.clear()


class GeographyTests(PlantTestCase):

    def test(self):
        pass

# TODO: maybe the following could be in a seperate file called
# profile.py or something that would profile everything in the plants
# module

#def main():
#    from optparse import OptionParser
#    parser = OptionParser()
#    parser.add_option('-v', '--verbose', dest='verbose', action='store_true',
#                      help='verbose output')
#    parser.add_option('-p', '--profile', dest='profile', action='store_true',
#                      help='print run times')
#    options, args = parser.parse_args()
#
#    import profile
#    import time
#    if options.profile:
#        t1 = time.time()
#        #profile.run('test_speciesStr()')
#        profile.run('profile()')
#        t2 = time.time()
#        print 'time: %s' % (t2-t1)
#    else:
#        print 'starting tests...'
#        test_speciesStr(options.verbose)
#        print 'done.'
#
#
#if __name__ == '__main__':
#    main()
