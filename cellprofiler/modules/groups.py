__doc__ = """
The <b>Groups</b> module organizes sets of images into groups.
<hr>
Once the images have been identified with the <b>Images</b> module (and/or optionally has
had metadata associated with the images using the <b>Metadata</b> module), and been given
a name by the <b>NamesAndTypes</b> module, you have the option of further sub-dividing
an image set into a <i>group</i> that is meant to be processed in a certain way.

<p>The key to understanding why grouping may be necessary is that CellProfiler processes
the input images sequentially and in the order given. If you have multiple collections of images
that are meant to be conceptually distinct from each other, CellProfiler will simply 
finish processing one collection and proceed to the next, ignoring any such distinctions unless 
told otherwise.</p>

<p>To illustrate this, below are two examples where the grouping concept can be useful or important:
<ul>
<li>If you are performing illumination correction for a screening experiment, we recommend 
that the illumination function (an image which represents the overall background fluorescence) 
be calculated on a per-plate basis. Since the illumination function is an aggregate of images from a
plate, running a pipeline must yield a single illumination function for each plate. Naively running 
a pipeline on all the images will create a single illumination function for <i>all</i> the images 
across all plates. Running this pipeline multiple times, once for each plate, will give the desired
result but would be tedious and time-consuming. In this case, CellProfiler can use image grouping 
for this purpose; if plate metadata can be defined by the <b>Metadata</b> module, grouping will enable you to
process images that have the same plate metadata together.</li>
<li>If you have time-lapse movie data that is in the form of individual image files, and you
are performing object tracking, it is important to indicate to CellProfiler that the end of a movie 
indicates the end of a distinct data set. Without doing so, CellProfiler will simply take the first frame
of the next movie as a continuation of the previous one. If each set of
files that comprise a movie is defined using the <b>Metadata</b> module, the relevant metadata can 
be used in this module to insure that object tracking only takes place within each movie.</li>
</ul>
</p>

<p>A grouping may be defined as according to any or as many of the metadata categories as defined by 
the <b>Metadata</b> module. Upon adding a metadata category, two tables will update in panels below
showing the resultant oragnization of the image data for each group.</p>
"""

#CellProfiler is distributed under the GNU General Public License.
#See the accompanying file LICENSE for details.
#
#Copyright (c) 2003-2009 Massachusetts Institute of Technology
#Copyright (c) 2009-2013 Broad Institute
#All rights reserved.
#
#Please see the AUTHORS file for credits.
#
#Website: http://www.cellprofiler.org

import logging
logger = logging.getLogger(__name__)
import numpy as np
import os

import cellprofiler.cpmodule as cpm
import cellprofiler.pipeline as cpp
import cellprofiler.settings as cps
import cellprofiler.measurements as cpmeas

class Groups(cpm.CPModule):
    variable_revision_number = 2
    module_name = "Groups"
    category = "File Processing"
    
    IDX_GROUPING_METADATA_COUNT = 1
    
    def create_settings(self):
        self.pipeline = None
        self.metadata_keys = {}
        
        self.module_explanation = cps.HTMLText("",content="""
            The %s module optionally allows you to split your list of images into image subsets
            (groups) which will be processed independently of each other. Examples of
            groupings include screening batches, microtiter plates, time-lapse movies, 
            etc."""%self.module_name, size=(30, 3))
        
        self.wants_groups = cps.Binary(
            "Do you want to group your images?", False)
        self.grouping_text = cps.HTMLText(
            "", content="""
            Each unique metadata value (or combination of values) 
            will be defined as a group""", size=(30, 2))
        self.grouping_metadata = []
        self.grouping_metadata_count = cps.HiddenCount(
            self.grouping_metadata,
            "grouping metadata count")
        self.add_grouping_metadata(can_remove = False)
        self.add_grouping_metadata_button = cps.DoSomething(
            "Add another metadata item", "Add", self.add_grouping_metadata)

        self.grouping_list = cps.Table("Grouping list", min_size = (300, 100),doc="""
            This list shows the unique values of the selected metadata; each of the
            unique values comprise a group. Also shown is the number of image sets that comprise that group; this
            is useful as a "sanity check", to make sure that the expected number of images are present. For example,
            if you are grouping by per-plate metadata from a 384-well assay with 2 sites per well consisting of 3 plates, 
            you woulld expect to see 3 groups (from 3 plates), with 384 wells &times; 2 sites/well &times;
            3 plates = 768 image sets in each.""")
        
        self.image_set_list = cps.Table("Image sets",doc="""
            This list displays the file name of location of each of the images that comprise the
            group. For example, if you are grouping by per-plate metadata from a 384-well assay with 2 sites per well 
            consisting of 3 plates, you would expect to see a table consisting of 768 rows.""")
        
    def add_grouping_metadata(self, can_remove = True):
        group = cps.SettingsGroup()
        self.grouping_metadata.append(group)
        def get_group_metadata_choices(pipeline):
            return self.get_metadata_choices(pipeline, group)
        if self.pipeline is not None:
            choices = get_group_metadata_choices(self.pipeline)
        else:
            choices = ["None"]
        group.append("metadata_choice", cps.Choice(
            "Metadata category", choices,
            choices_fn = get_group_metadata_choices,doc="""
            Specify the metadata category with which to define a group. Once a selection
            is made, the two listings below will display the updated values.
            
            <p>As an example, an experiment consists of a set of plates of images with 
            two image channels ("w1" and "w2") containing
            well and site metadata extracted using the <b>Metadata</b> module. A set of
            images from two sites in well A01 might be described using the following:
            <table border="1" align="center">
            <tr><th>File name</th><th>Plate</th><th> Well</th><th>Site</th><th>Wavelength</th></tr>
            <tr><td>P-12345_<span style="color:#ce5f33">A01</font>_<span style="color:#3dce33>s1</font>_<span style="color:#33bbce">w1</font>.tif</td><td>P-12345</td><td>A01</td><td>s1</td><td>w1</td></tr>
            <tr><td>P-12345_<span style="color:#ce5f33">A01</font>_<span style="color:#3dce33>s1</font>_<span style="color:#33bbce">w2</font>.tif</td><td>P-12345</td><td>A01</td><td>s1</td><td>w2</td></tr>
            <tr><td>P-12345_<span style="color:#ce5f33">A01</font>_<span style="color:#3dce33>s2</font>_<span style="color:#33bbce">w1</font>.tif</td><td>P-12345</td><td>A01</td><td>s2</td><td>w1</td></tr>
            <tr><td>P-12345_<span style="color:#ce5f33">A01</font>_<span style="color:#3dce33>s2</font>_<span style="color:#33bbce">w2</font>.tif</td><td>P-12345</td><td>A01</td><td>s2</td><td>w2</td></tr>
            <tr><td>P-12345_<span style="color:#ce5f33">B01</font>_<span style="color:#3dce33>s1</font>_<span style="color:#33bbce">w1</font>.tif</td><td>P-12345</td><td>A01</td><td>s1</td><td>w1</td></tr>
            <tr><td>P-12345_<span style="color:#ce5f33">B01</font>_<span style="color:#3dce33>s1</font>_<span style="color:#33bbce">w2</font>.tif</td><td>P-12345</td><td>A01</td><td>s1</td><td>w2</td></tr>
            <tr><td>P-12345_<span style="color:#ce5f33">B01</font>_<span style="color:#3dce33>s2</font>_<span style="color:#33bbce">w1</font>.tif</td><td>P-12345</td><td>A01</td><td>s2</td><td>w1</td></tr>
            <tr><td>P-12345_<span style="color:#ce5f33">B01</font>_<span style="color:#3dce33>s2</font>_<span style="color:#33bbce">w2</font>.tif</td><td>P-12345</td><td>A01</td><td>s2</td><td>w2</td></tr>
            <tr><td>2-ABCDF_<span style="color:#ce5f33">A01</font>_<span style="color:#3dce33>s1</font>_<span style="color:#33bbce">w1</font>.tif</td><td>2-ABCDF_</td><td>A01</td><td>s1</td><td>w1</td></tr>
            <tr><td>2-ABCDF_<span style="color:#ce5f33">A01</font>_<span style="color:#3dce33>s1</font>_<span style="color:#33bbce">w2</font>.tif</td><td>2-ABCDF_</td><td>A01</td><td>s1</td><td>w2</td></tr>
            <tr><td>2-ABCDF_<span style="color:#ce5f33">A01</font>_<span style="color:#3dce33>s2</font>_<span style="color:#33bbce">w1</font>.tif</td><td>2-ABCDF_</td><td>A01</td><td>s2</td><td>w1</td></tr>
            <tr><td>2-ABCDF_<span style="color:#ce5f33">A01</font>_<span style="color:#3dce33>s2</font>_<span style="color:#33bbce">w2</font>.tif</td><td>2-ABCDF_</td><td>A01</td><td>s2</td><td>w2</td></tr>
            <tr><td>2-ABCDF_<span style="color:#ce5f33">B01</font>_<span style="color:#3dce33>s1</font>_<span style="color:#33bbce">w1</font>.tif</td><td>2-ABCDF_</td><td>A01</td><td>s1</td><td>w1</td></tr>
            <tr><td>2-ABCDF_<span style="color:#ce5f33">B01</font>_<span style="color:#3dce33>s1</font>_<span style="color:#33bbce">w2</font>.tif</td><td>2-ABCDF_</td><td>A01</td><td>s1</td><td>w2</td></tr>
            <tr><td>2-ABCDF_<span style="color:#ce5f33">B01</font>_<span style="color:#3dce33>s2</font>_<span style="color:#33bbce">w1</font>.tif</td><td>2-ABCDF_</td><td>A01</td><td>s2</td><td>w1</td></tr>
            <tr><td>2-ABCDF_<span style="color:#ce5f33">B01</font>_<span style="color:#3dce33>s2</font>_<span style="color:#33bbce">w2</font>.tif</td><td>2-ABCDF_</td><td>A01</td><td>s2</td><td>w2</td></tr>
            </table>
            </p>
            <p>Selecting the "Plate" metadata as the metadata category will create two groups based on the unique plate identifiers (P-12345 and 2-ABCDF):
            <table border="1" align="center">
            <tr><th>Group number</th><th>Plate</th><th>Well</td><td>Site</td><td>w1</td><td>w2</td></tr>
            <tr><td>1</td><td>P-12345</td><td>A01</td><td>s1</td><td>P-12345_<span style="color:#ce5f33">A01</font>_<span style="color:#3dce33">s1</font>_<span style="color:#33bbce">w1</font>.tif</td><td>P-12345_<span style="color:#ce5f33">A01</font>_<span style="color:#3dce33">s1</font>_<span style="color:#33bbce">w2</font>.tif</td></tr>
            <tr><td>1</td><td>P-12345</td><td>B01</td><td>s1</td><td>P-12345_<span style="color:#ce5f33">B01</font>_<span style="color:#3dce33">s1</font>_<span style="color:#33bbce">w1</font>.tif</td><td>P-12345_<span style="color:#ce5f33">B01</font>_<span style="color:#3dce33">s1</font>_<span style="color:#33bbce">w2</font>.tif</td></tr>
            <tr><td>2</td><td>2-ABCDF</td><td>A01</td><td>s2</td><td>2-ABCDF_<span style="color:#ce5f33">A01</font>_<span style="color:#3dce33">s2</font>_<span style="color:#33bbce">w1</font>.tif</td><td>2-ABCDF_<span style="color:#ce5f33">A01</font>_<span style="color:#3dce33">s2</font>_<span style="color:#33bbce">w2</font>.tif</td></tr>
            <tr><td>2</td><td>2-ABCDF</td><td>A01</td><td>s2</td><td>2-ABCDF_<span style="color:#ce5f33">B01</font>_<span style="color:#3dce33">s2</font>_<span style="color:#33bbce">w1</font>.tif</td><td>2-ABCDF_<span style="color:#ce5f33">B01</font>_<span style="color:#3dce33">s2</font>_<span style="color:#33bbce">w2</font>.tif</td></tr>
            </table>
            Selecting "Plate" and "Well" metadata as the category will create 
            In order to match the w1 and w2 channels with their respective well and site metadata,
            you would select the "Well" metadata for both channels, followed by the "Site" metadata
            for both channels. If both files have the same well and site metadata, CellProfiler will 
            match the file in one channel with well A01 and site 1 with the file in the
            other channel with well A01 and site 1 and so on, to create an image set like the following:
            <table border="1" align="center">
            <tr><th>Image set key</th><th>Channel</th><th>Channel</th></tr>
            <tr><td>Well</td><td>Site</td><td>w1</td><td>w2</td></tr>
            <tr><td>A01</td><td>s1</td><td>P-12345_<span style="color:#ce5f33">A01</font>_<span style="color:#3dce33">s1</font>_<span style="color:#33bbce">w1</font>.tif</td><td>P-12345_<span style="color:#ce5f33">A01</font>_<span style="color:#3dce33">s1</font>_<span style="color:#33bbce">w2</font>.tif</td></tr>
            <tr><td>A01</td><td>s2</td><td>P-12345_<span style="color:#ce5f33">A01</font>_<span style="color:#3dce33">s2</font>_<span style="color:#33bbce">w1</font>.tif</td><td>P-12345_<span style="color:#ce5f33">A01</font>_<span style="color:#3dce33">s2</font>_<span style="color:#33bbce">w2</font>.tif</td></tr>
            </table>
            </p>"""))
        
        group.append("divider", cps.Divider())
        group.can_remove = can_remove
        if can_remove:
            group.append("remover", cps.RemoveSettingButton(
                "Remove the above metadata item", "Remove", 
                self.grouping_metadata, group))

    def get_metadata_choices(self, pipeline, group):
        if self.pipeline is not None:
            return sorted(self.metadata_keys)
        #
        # Unfortunate - an expensive operation to find the possible metadata
        #               keys from one of the columns in an image set.
        # Just fake it into having something that will work
        #
        return [group.metadata_choice.value]
        
    def settings(self):
        result = [self.wants_groups, self.grouping_metadata_count]
        for group in self.grouping_metadata:
            result += [group.metadata_choice]
        return result
            
    def visible_settings(self):
        result = [self.module_explanation, self.wants_groups]
        if self.wants_groups:
            result += [self.grouping_text]
            for group in self.grouping_metadata:
                result += [ group.metadata_choice]
                if group.can_remove:
                    result += [group.remover]
                result += [ group.divider ]
            result += [self.add_grouping_metadata_button, 
                       self.grouping_list, self.image_set_list]
        return result
    
    def prepare_settings(self, setting_values):
        nmetadata = int(setting_values[self.IDX_GROUPING_METADATA_COUNT])
        while len(self.grouping_metadata) > nmetadata:
            del self.grouping_metadata[-1]
            
        while len(self.grouping_metadata) < nmetadata:
            self.add_grouping_metadata()
            
    def on_activated(self, workspace):
        self.pipeline = workspace.pipeline
        self.workspace = workspace
        assert isinstance(self.pipeline, cpp.Pipeline)
        if self.wants_groups:
            self.image_sets_initialized = True
            workspace.refresh_image_set()
            self.metadata_keys = []
            m = workspace.measurements
            if m.image_set_count > 0:
                assert isinstance(m, cpmeas.Measurements)
                for feature_name in m.get_feature_names(cpmeas.IMAGE):
                    if feature_name.startswith(cpmeas.C_METADATA):
                        self.metadata_keys.append(
                            feature_name[(len(cpmeas.C_METADATA)+1):])
            is_valid = True
            for group in self.grouping_metadata:
                try:
                    group.metadata_choice.test_valid(self.pipeline)
                except:
                    is_valid = False
            if is_valid:
                self.update_tables()
        else:
            self.image_sets_initialized = False
        
    def on_deactivated(self):
        self.pipeline = None
        
    def on_setting_changed(self, setting, pipeline):
        if (setting == self.wants_groups and self.wants_groups and
            not self.image_sets_initialized):
            workspace = self.workspace
            self.on_deactivated()
            self.on_activated(workspace)
            
        #
        # Unfortunately, test_valid has the side effect of getting
        # the choices set which is why it's called here
        #
        is_valid = True
        for group in self.grouping_metadata:
            try:
                group.metadata_choice.test_valid(pipeline)
            except:
                is_valid = False
        if is_valid:
            self.update_tables()
        
    def update_tables(self):
        if self.wants_groups:
            try:
                self.workspace.refresh_image_set()
            except:
                return
            m = self.workspace.measurements
            assert isinstance(m, cpmeas.Measurements)
            channel_descriptors = m.get_channel_descriptors()
            
            self.grouping_list.clear_columns()
            self.grouping_list.clear_rows()
            self.image_set_list.clear_columns()
            self.image_set_list.clear_rows()
            metadata_key_names = [group.metadata_choice.value
                                  for group in self.grouping_metadata]
            metadata_feature_names = ["_".join((cpmeas.C_METADATA, key))
                                      for key in metadata_key_names]
            metadata_key_names =  [
                x[(len(cpmeas.C_METADATA)+1):]
                for x in metadata_feature_names]
            image_set_feature_names = [
                cpmeas.GROUP_NUMBER, cpmeas.GROUP_INDEX] + metadata_feature_names
            self.image_set_list.insert_column(0, "Group number")
            self.image_set_list.insert_column(1, "Group index")
            
            for i, key in enumerate(metadata_key_names):
                for l, offset in ((self.grouping_list, 0),
                                  (self.image_set_list, 2)):
                    l.insert_column(i+offset, "Group: %s" % key)
                
            self.grouping_list.insert_column(len(metadata_key_names), "Count")
            
            image_numbers = m.get_image_numbers()
            group_indexes = m[cpmeas.IMAGE, 
                              cpmeas.GROUP_INDEX, 
                              image_numbers][:]
            group_numbers = m[cpmeas.IMAGE, 
                              cpmeas.GROUP_NUMBER, 
                              image_numbers][:]
            counts = np.bincount(group_numbers)
            first_indexes = np.argwhere(group_indexes == 1).flatten()
            group_keys = [
                m[cpmeas.IMAGE, feature, image_numbers]
                for feature in metadata_feature_names]
            k_count = sorted([(group_numbers[i], 
                               [x[i] for x in group_keys], 
                               counts[group_numbers[i]])
                              for i in first_indexes])
            for group_number, group_key_values, c in k_count:
                row = group_key_values + [c]
                self.grouping_list.data.append(row)

            for i, iscd in enumerate(channel_descriptors):
                assert isinstance(iscd, cpp.Pipeline.ImageSetChannelDescriptor)
                image_name = iscd.name
                idx = len(image_set_feature_names)
                self.image_set_list.insert_column(idx, "Path: %s" % image_name)
                self.image_set_list.insert_column(idx+1, "File: %s" % image_name)
                if iscd.channel_type == iscd.CT_OBJECTS:
                    image_set_feature_names.append(
                        cpmeas.C_OBJECTS_PATH_NAME + "_" + iscd.name)
                    image_set_feature_names.append(
                        cpmeas.C_OBJECTS_FILE_NAME + "_" + iscd.name)
                else:
                    image_set_feature_names.append(
                        cpmeas.C_PATH_NAME + "_" + iscd.name)
                    image_set_feature_names.append(
                        cpmeas.C_FILE_NAME + "_" + iscd.name)

            all_features = [m[cpmeas.IMAGE, ftr, image_numbers]
                            for ftr in image_set_feature_names]
            order = np.lexsort((group_indexes, group_numbers))
                
            for idx in order:
                row = [unicode(x[idx]) for x in all_features]
                self.image_set_list.data.append(row)
            
    def get_groupings(self, workspace):
        '''Return the image groupings of the image sets in an image set list
        
        returns a tuple of key_names and group_list:
        key_names - the names of the keys that identify the groupings
        group_list - a sequence composed of two-tuples.
                     the first element of the tuple has the values for
                     the key_names for this group.
                     the second element of the tuple is a sequence of
                     image numbers comprising the image sets of the group
        For instance, an experiment might have key_names of 'Metadata_Row'
        and 'Metadata_Column' and a group_list of:
        [ ({'Row':'A','Column':'01'), [0,96,192]),
          (('Row':'A','Column':'02'), [1,97,193]),... ]
        '''
        if not self.wants_groups:
            return
        key_list = self.get_grouping_tags()
        m = workspace.measurements
        if any([key not in m.get_feature_names(cpmeas.IMAGE) for key in key_list]):
            # Premature execution of get_groupings if module is mis-configured
            return None
        return key_list, m.get_groupings(key_list)
    
    def get_grouping_tags(self):
        '''Return the metadata keys used for grouping'''
        if not self.wants_groups:
            return None
        return ["_".join((cpmeas.C_METADATA, g.metadata_choice.value))
                for g in self.grouping_metadata]
    
    def change_causes_prepare_run(self, setting):
        '''Return True if changing the setting passed changes the image sets
        
        setting - the setting that was changed
        '''
        return setting in self.settings()
    
    def is_load_module(self):
        '''Marks this module as a module that affects the image sets
        
        Groups is a load module because it can reorder image sets, but only
        if grouping is turned on.
        '''
        return self.wants_groups.value
    
    def is_input_module(self):
        return True
            
    def prepare_run(self, workspace):
        '''Reorder the image sets and assign group number and index'''
        if workspace.pipeline.in_batch_mode():
            return True
        
        if not self.wants_groups:
            return True
        
        result = self.get_groupings(workspace)
        if result is None:
            return False
        key_list, groupings = result
        #
        # Sort the groupings by key
        #
        groupings = sorted(groupings)
        #
        # Create arrays of group number, group_index and image_number
        #
        group_numbers = np.hstack([
            np.ones(len(image_numbers), int) * (i + 1)
            for i, (keys, image_numbers) in enumerate(groupings)])
        group_indexes = np.hstack([
            np.arange(len(image_numbers)) + 1
            for keys, image_numbers in groupings])
        image_numbers = np.hstack([
            image_numbers for keys, image_numbers in groupings])
        order = np.lexsort((group_indexes, group_numbers ))
        group_numbers = group_numbers[order]
        group_indexes = group_indexes[order]
        
        m = workspace.measurements
        assert isinstance(m, cpmeas.Measurements)
        #
        # Downstream processing requires that image sets be ordered by
        # increasing group number, then increasing group index.
        #
        new_image_numbers = np.zeros(np.max(image_numbers) + 1, int)
        new_image_numbers[image_numbers[order]] = np.arange(len(image_numbers))+1
        m.reorder_image_measurements(new_image_numbers)
        m.add_all_measurements(cpmeas.IMAGE, cpmeas.GROUP_NUMBER, group_numbers)
        m.add_all_measurements(cpmeas.IMAGE, cpmeas.GROUP_INDEX, group_indexes)
        m.set_grouping_tags(self.get_grouping_tags())
        return True
        
    def run(self, workspace):
        pass
    
    def get_measurement_columns(self, pipeline):
        '''Return the measurments recorded by this module
        
        GroupNumber and GroupIndex are accounted for by the pipeline itself.
        '''
        result = []
        if self.wants_groups:
            result.append((cpmeas.EXPERIMENT, 
                           cpmeas.M_GROUPING_TAGS, 
                           cpmeas.COLTYPE_VARCHAR))
            #
            # These are bound to be produced elsewhere, but it is quite 
            # computationally expensive to find that out. If they are
            # duplicated by another module, no big deal.
            #
            for ftr in self.get_grouping_tags():
                result.append((cpmeas.IMAGE, ftr, cpmeas.COLTYPE_VARCHAR))
        return result
    
    def upgrade_settings(self, setting_values, variable_revision_number,
                         module_name, from_matlab):
        if variable_revision_number == 1:
            #
            # Remove the image name from the settings
            #
            new_setting_values = \
                setting_values[:(self.IDX_GROUPING_METADATA_COUNT+1)]
            for i in range(int(setting_values[self.IDX_GROUPING_METADATA_COUNT])):
                new_setting_values.append(
                    setting_values[self.IDX_GROUPING_METADATA_COUNT + 2 + i*2])
            setting_values = new_setting_values
            variable_revision_number = 2
        return setting_values, variable_revision_number, from_matlab