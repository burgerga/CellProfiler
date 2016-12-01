'''<b>RescaleIntensity</b> changes the intensity range of an image to your
desired specifications.
<hr>
This module lets you rescale the intensity of the input images by any of several
methods. You should use caution when interpreting intensity and texture measurements
derived from images that have been rescaled because certain options for this module
do not preserve the relative intensities from image to image.
'''

import numpy
import skimage.exposure

import cellprofiler.image
import cellprofiler.measurement
import cellprofiler.module
import cellprofiler.setting

M_STRETCH = 'Stretch each image to use the full intensity range'
M_MANUAL_INPUT_RANGE = 'Choose specific values to be reset to the full intensity range'
M_MANUAL_IO_RANGE = 'Choose specific values to be reset to a custom range'
M_DIVIDE_BY_IMAGE_MINIMUM = "Divide by the image's minimum"
M_DIVIDE_BY_IMAGE_MAXIMUM = "Divide by the image's maximum"
M_DIVIDE_BY_VALUE = 'Divide each image by the same value'
M_DIVIDE_BY_MEASUREMENT = 'Divide each image by a previously calculated value'
M_SCALE_BY_IMAGE_MAXIMUM = "Match the image's maximum to another image's maximum"

M_ALL = [M_STRETCH, M_MANUAL_INPUT_RANGE, M_MANUAL_IO_RANGE,
         M_DIVIDE_BY_IMAGE_MINIMUM, M_DIVIDE_BY_IMAGE_MAXIMUM,
         M_DIVIDE_BY_VALUE, M_DIVIDE_BY_MEASUREMENT,
         M_SCALE_BY_IMAGE_MAXIMUM]

R_SCALE = 'Scale similarly to others'
R_MASK = 'Mask pixels'
R_SET_TO_ZERO = 'Set to zero'
R_SET_TO_CUSTOM = 'Set to custom value'
R_SET_TO_ONE = 'Set to one'

LOW_ALL_IMAGES = 'Minimum of all images'
LOW_EACH_IMAGE = 'Minimum for each image'
CUSTOM_VALUE = 'Custom'
LOW_ALL = [CUSTOM_VALUE, LOW_EACH_IMAGE, LOW_ALL_IMAGES]

HIGH_ALL_IMAGES = 'Maximum of all images'
HIGH_EACH_IMAGE = 'Maximum for each image'

HIGH_ALL = [CUSTOM_VALUE, HIGH_EACH_IMAGE, HIGH_ALL_IMAGES]


class RescaleIntensity(cellprofiler.module.Module):
    module_name = "RescaleIntensity"
    category = "Image Processing"
    variable_revision_number = 3

    def create_settings(self):
        self.image_name = cellprofiler.setting.ImageNameSubscriber(
                "Select the input image", cellprofiler.setting.NONE, doc=
                '''Select the image to be rescaled.''')

        self.rescaled_image_name = cellprofiler.setting.ImageNameProvider(
                "Name the output image", "RescaledBlue", doc=
                '''Enter the name of output rescaled image.''')

        self.rescale_method = cellprofiler.setting.Choice(
                'Rescaling method',
                choices=M_ALL, doc='''
            There are a number of options for rescaling the input image:
            <ul>
            <li><i>%(M_STRETCH)s:</i> Find the minimum and maximum values within the unmasked part of the image
            (or the whole image if there is no mask) and rescale every pixel so that
            the minimum has an intensity of zero and the maximum has an intensity of one.</li>
            <li><i>%(M_MANUAL_INPUT_RANGE)s:</i> Pixels are
            scaled from their user-specified original range to the range 0 to 1.
            Options are available to handle values outside of the original range.<br>
            To convert 12-bit images saved in 16-bit format to the correct range,
            use the range 0 to 0.0625. The value 0.0625 is equivalent
            to 2<sup>12</sup> divided by 2<sup>16</sup>, so it will convert a 16 bit image containing
            only 12 bits of data to the proper range.</li>
            <li><i>%(M_MANUAL_IO_RANGE)s:</i> Pixels are scaled from their original range to
            the new target range. Options are available to handle values outside
            of the original range.</li>
            <li><i>%(M_DIVIDE_BY_IMAGE_MINIMUM)s:</i> Divide the intensity value of each pixel
            by the image's minimum intensity value so that all pixel intensities are equal to or
            greater than 1. The rescaled image can serve as an illumination correction function in
            <b>CorrectIlluminationApply</b>.</li>
            <li><i>%(M_DIVIDE_BY_IMAGE_MAXIMUM)s:</i> Divide the intensity value of each pixel by the
            image's maximum intensity value so that all pixel intensities are less than or equal to 1.</li>
            <li><i>%(M_DIVIDE_BY_VALUE)s:</i> Divide the intensity value of each pixel by the value entered.</li>
            <li><i>%(M_DIVIDE_BY_MEASUREMENT)s:</i> The intensity value of each pixel is divided by some
            previously calculated measurement. This measurement can be the output of some other module
            or can be a value loaded by the <b>Metadata</b> module.</li>
            <li><i>%(M_SCALE_BY_IMAGE_MAXIMUM)s:</i> Scale an image so that its maximum value is the
            same as the maximum value within the reference image.</li>
            </ul>''' % globals())

        self.wants_automatic_low = cellprofiler.setting.Choice(
                'Method to calculate the minimum intensity',
                LOW_ALL, doc="""
            <i>(Used only if "%(M_MANUAL_IO_RANGE)s" is selected)</i><br>
            This setting controls how the minimum intensity is determined.
            <ul>
            <li><i>%(CUSTOM_VALUE)s:</i> Enter the minimum intensity manually below.</li>
            <li><i>%(LOW_EACH_IMAGE)s</i>: use the lowest intensity in this image
            as the minimum intensity for rescaling</li>
            <li><i>%(LOW_ALL_IMAGES)s</i>: use the lowest intensity from all images
            in the image group or the experiment if grouping is not being used.
            <b>Note:</b> Choosing this option may have undesirable results for
            a large ungrouped experiment split into a number of batches. Each batch
            will open all images from the chosen channel at the start of the run.
            This sort of synchronized action may have a severe impact on your
            network file system.</li>
            </ul>
            """ % globals())

        self.wants_automatic_high = cellprofiler.setting.Choice(
                'Method to calculate the maximum intensity',
                HIGH_ALL, doc="""
            <i>(Used only if "%(M_MANUAL_IO_RANGE)s" is selected)</i><br>
            This setting controls how the maximum intensity is determined.
            <ul>
            <li><i>%(CUSTOM_VALUE)s</i>: Enter the maximum intensity manually below.</li>
            <li><i>%(HIGH_EACH_IMAGE)s</i>: Use the highest intensity in this image
            as the maximum intensity for rescaling</li>
            <li><i>%(HIGH_ALL_IMAGES)s</i>: Use the highest intensity from all images
            in the image group or the experiment if grouping is not being used.
            <b>Note:</b> Choosing this option may have undesirable results for
            a large ungrouped experiment split into a number of batches. Each batch
            will open all images from the chosen channel at the start of the run.
            This sort of synchronized action may have a severe impact on your
            network file system.</li>
            </ul>
            """ % globals())

        self.source_low = cellprofiler.setting.Float('Lower intensity limit for the input image', 0)

        self.source_high = cellprofiler.setting.Float('Upper intensity limit for the input image', 1)

        self.source_scale = cellprofiler.setting.FloatRange('Intensity range for the input image', (0, 1))

        self.dest_scale = cellprofiler.setting.FloatRange('Intensity range for the output image', (0, 1))

        self.matching_image_name = cellprofiler.setting.ImageNameSubscriber(
                "Select image to match in maximum intensity", cellprofiler.setting.NONE, doc="""
            <i>(Used only if "%(M_SCALE_BY_IMAGE_MAXIMUM)s" is selected)</i><br>
            Select the image whose maximum you want the rescaled image to match.""" % globals())

        self.divisor_value = cellprofiler.setting.Float(
                "Divisor value",
                1, minval=numpy.finfo(float).eps, doc="""
            <i>(Used only if "%(M_DIVIDE_BY_VALUE)s" is selected)</i><br>
            Enter the value to use as the divisor for the final image.""" % globals())

        self.divisor_measurement = cellprofiler.setting.Measurement(
                "Divisor measurement",
                lambda: cellprofiler.measurement.IMAGE, doc="""
            <i>(Used only if "%(M_DIVIDE_BY_MEASUREMENT)s" is selected)</i><br>
            Select the measurement value to use as the divisor for the final image.""" % globals())

    def settings(self):
        return [
            self.image_name,
            self.rescaled_image_name,
            self.rescale_method,
            self.wants_automatic_low,
            self.wants_automatic_high,
            self.source_low,
            self.source_high,
            self.source_scale,
            self.dest_scale,
            self.matching_image_name,
            self.divisor_value,
            self.divisor_measurement
        ]

    def visible_settings(self):
        result = [self.image_name, self.rescaled_image_name,
                  self.rescale_method]
        if self.rescale_method in (M_MANUAL_INPUT_RANGE, M_MANUAL_IO_RANGE):
            result += [self.wants_automatic_low]
            if self.wants_automatic_low.value == CUSTOM_VALUE:
                if self.wants_automatic_high != CUSTOM_VALUE:
                    result += [self.source_low, self.wants_automatic_high]
                else:
                    result += [self.wants_automatic_high, self.source_scale]
            else:
                result += [self.wants_automatic_high]
                if self.wants_automatic_high == CUSTOM_VALUE:
                    result += [self.source_high]
        if self.rescale_method == M_MANUAL_IO_RANGE:
            result += [self.dest_scale]

        if self.rescale_method == M_SCALE_BY_IMAGE_MAXIMUM:
            result += [self.matching_image_name]
        elif self.rescale_method == M_DIVIDE_BY_MEASUREMENT:
            result += [self.divisor_measurement]
        elif self.rescale_method == M_DIVIDE_BY_VALUE:
            result += [self.divisor_value]
        return result

    def set_automatic_minimum(self, image_set_list, value):
        d = self.get_dictionary(image_set_list)
        d[LOW_ALL_IMAGES] = value

    def get_automatic_minimum(self, image_set_list):
        d = self.get_dictionary(image_set_list)
        return d[LOW_ALL_IMAGES]

    def set_automatic_maximum(self, image_set_list, value):
        d = self.get_dictionary(image_set_list)
        d[HIGH_ALL_IMAGES] = value

    def get_automatic_maximum(self, image_set_list):
        d = self.get_dictionary(image_set_list)
        return d[HIGH_ALL_IMAGES]

    def prepare_group(self, workspace, grouping, image_numbers):
        '''Handle initialization per-group

        pipeline - the pipeline being run
        image_set_list - the list of image sets for the whole experiment
        grouping - a dictionary that describes the key for the grouping.
                   For instance, { 'Metadata_Row':'A','Metadata_Column':'01'}
        image_numbers - a sequence of the image numbers within the
                   group (image sets can be retreved as
                   image_set_list.get_image_set(image_numbers[i]-1)

        We use prepare_group to compute the minimum or maximum values
        among all images in the group for certain values of
        "wants_automatic_[low,high]".
        '''
        if (self.wants_automatic_high != HIGH_ALL_IMAGES and
                    self.wants_automatic_low != LOW_ALL_IMAGES):
            return True

        title = "#%d: RescaleIntensity for %s" % (
            self.module_num, self.image_name.value)
        message = ("RescaleIntensity will process %d images while "
                   "preparing for run" % (len(image_numbers)))
        min_value = None
        max_value = None
        for w in workspace.pipeline.run_group_with_yield(
                workspace, grouping, image_numbers, self, title, message):
            image_set = w.image_set
            image = image_set.get_image(self.image_name.value,
                                        must_be_grayscale=True,
                                        cache=False)
            if self.wants_automatic_high == HIGH_ALL_IMAGES:
                if image.has_mask:
                    vmax = numpy.max(image.pixel_data[image.mask])
                else:
                    vmax = numpy.max(image.pixel_data)
                    max_value = vmax if max_value is None else max(max_value, vmax)

            if self.wants_automatic_low == LOW_ALL_IMAGES:
                if image.has_mask:
                    vmin = numpy.min(image.pixel_data[image.mask])
                else:
                    vmin = numpy.min(image.pixel_data)
                    min_value = vmin if min_value is None else min(min_value, vmin)

        if self.wants_automatic_high == HIGH_ALL_IMAGES:
            self.set_automatic_maximum(workspace.image_set_list, max_value)
        if self.wants_automatic_low == LOW_ALL_IMAGES:
            self.set_automatic_minimum(workspace.image_set_list, min_value)

    def is_aggregation_module(self):
        '''We scan through all images in a group in some cases'''
        return ((self.wants_automatic_high == HIGH_ALL_IMAGES) or
                (self.wants_automatic_low == LOW_ALL_IMAGES))

    def run(self, workspace):
        input_image = workspace.image_set.get_image(self.image_name.value)
        output_mask = None
        if self.rescale_method == M_STRETCH:
            output_image = self.stretch(input_image)
        elif self.rescale_method == M_MANUAL_INPUT_RANGE:
            output_image = self.manual_input_range(input_image, workspace)
        elif self.rescale_method == M_MANUAL_IO_RANGE:
            output_image = self.manual_io_range(input_image, workspace)
        elif self.rescale_method == M_DIVIDE_BY_IMAGE_MINIMUM:
            output_image = self.divide_by_image_minimum(input_image)
        elif self.rescale_method == M_DIVIDE_BY_IMAGE_MAXIMUM:
            output_image = self.divide_by_image_maximum(input_image)
        elif self.rescale_method == M_DIVIDE_BY_VALUE:
            output_image = self.divide_by_value(input_image)
        elif self.rescale_method == M_DIVIDE_BY_MEASUREMENT:
            output_image = self.divide_by_measurement(workspace, input_image)
        elif self.rescale_method == M_SCALE_BY_IMAGE_MAXIMUM:
            output_image = self.scale_by_image_maximum(workspace, input_image)
        if output_mask is not None:
            rescaled_image = cellprofiler.image.Image(output_image,
                                                      mask=output_mask,
                                                      parent_image=input_image,
                                                      convert=False)
        else:
            rescaled_image = cellprofiler.image.Image(output_image,
                                                      parent_image=input_image,
                                                      convert=False)
        workspace.image_set.add(self.rescaled_image_name.value, rescaled_image)
        if self.show_window:
            workspace.display_data.image_data = [input_image.pixel_data,
                                                 rescaled_image.pixel_data]

    def display(self, workspace, figure):
        '''Display the input image and rescaled image'''
        figure.set_subplots((2, 1))

        for image_name, i, j in ((self.image_name, 0, 0),
                                 (self.rescaled_image_name, 1, 0)):
            image_name = image_name.value
            pixel_data = workspace.display_data.image_data[i]
            if pixel_data.ndim == 2:
                figure.subplot_imshow_grayscale(i, j, pixel_data,
                                                title=image_name,
                                                vmin=0, vmax=1,
                                                sharexy=figure.subplot(0, 0))
            else:
                figure.subplot_imshow(i, j, pixel_data, title=image_name,
                                      normalize=False,
                                      sharexy=figure.subplot(0, 0))

    def rescale(self, image, in_range, out_range=(0.0, 1.0)):
        data = image.pixel_data

        rescaled = skimage.exposure.rescale_intensity(data, in_range=in_range, out_range=out_range)

        return rescaled

    def stretch(self, input_image):
        data = input_image.pixel_data

        mask = input_image.mask

        in_range = (min(data[mask]), max(data[mask]))

        return self.rescale(input_image, in_range)

    def manual_input_range(self, input_image, workspace):
        in_range = self.get_source_range(input_image, workspace)

        return self.rescale(input_image, in_range)

    def manual_io_range(self, input_image, workspace):
        in_range = self.get_source_range(input_image, workspace)

        out_range = (self.dest_scale.min, self.dest_scale.max)

        return self.rescale(input_image, in_range, out_range)

    def divide(self, data, value):
        if value == 0.0:
            raise ZeroDivisionError("Cannot divide pixel intensity by 0.")

        return data / float(value)

    def divide_by_image_minimum(self, input_image):
        data = input_image.pixel_data

        src_min = numpy.min(data[input_image.mask])

        return self.divide(data, src_min)

    def divide_by_image_maximum(self, input_image):
        data = input_image.pixel_data

        src_max = numpy.max(data[input_image.mask])

        return self.divide(data, src_max)

    def divide_by_value(self, input_image):
        return self.divide(input_image.pixel_data, self.divisor_value.value)

    def divide_by_measurement(self, workspace, input_image):
        m = workspace.measurements

        value = m.get_current_image_measurement(self.divisor_measurement.value)

        return self.divide(input_image.pixel_data, value)

    def scale_by_image_maximum(self, workspace, input_image):
        ###
        # Scale the image by the maximum of another image
        #
        # Find the maximum value within the unmasked region of the input
        # and reference image. Multiply by the reference maximum, divide
        # by the input maximum to scale the input image to the same
        # range as the reference image
        ###
        image_max = numpy.max(input_image.pixel_data[input_image.mask])

        if image_max == 0:
            return input_image.pixel_data

        reference_image = workspace.image_set.get_image(self.matching_image_name.value)

        reference_pixels = reference_image.pixel_data[reference_image.mask]

        reference_max = numpy.max(reference_pixels)

        return self.divide(input_image.pixel_data * reference_max, image_max)

    def get_source_range(self, input_image, workspace):
        '''Get the source range, accounting for automatically computed values'''
        if (self.wants_automatic_high == CUSTOM_VALUE and
                    self.wants_automatic_low == CUSTOM_VALUE):
            return self.source_scale.min, self.source_scale.max

        if (self.wants_automatic_low == LOW_EACH_IMAGE or
                    self.wants_automatic_high == HIGH_EACH_IMAGE):
            input_pixels = input_image.pixel_data
            if input_image.has_mask:
                input_pixels = input_pixels[input_image.mask]

        if self.wants_automatic_low == LOW_ALL_IMAGES:
            src_min = self.get_automatic_minimum(workspace.image_set_list)
        elif self.wants_automatic_low == LOW_EACH_IMAGE:
            src_min = numpy.min(input_pixels)
        else:
            src_min = self.source_low.value
        if self.wants_automatic_high.value == HIGH_ALL_IMAGES:
            src_max = self.get_automatic_maximum(workspace.image_set_list)
        elif self.wants_automatic_high == HIGH_EACH_IMAGE:
            src_max = numpy.max(input_pixels)
        else:
            src_max = self.source_high.value
        return src_min, src_max

    def upgrade_settings(self, setting_values, variable_revision_number, module_name, from_matlab):
        if variable_revision_number == 1:
            #
            # wants_automatic_low (# 3) and wants_automatic_high (# 4)
            # changed to a choice: yes = each, no = custom
            #
            setting_values = list(setting_values)

            for i, automatic in ((3, LOW_EACH_IMAGE), (4, HIGH_EACH_IMAGE)):
                if setting_values[i] == cellprofiler.setting.YES:
                    setting_values[i] = automatic
                else:
                    setting_values[i] = CUSTOM_VALUE

            variable_revision_number = 2

        if variable_revision_number == 2:
            #
            # removed settings low_truncation_choice, custom_low_truncation,
            # high_truncation_choice, custom_high_truncation (#9-#12)
            #
            setting_values = setting_values[:9] + setting_values[13:]

            variable_revision_number = 3

        return setting_values, variable_revision_number, False
