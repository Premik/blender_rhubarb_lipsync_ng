import unittest


import sample_project
from helper import skip_no_aud


class PropertiesTest(unittest.TestCase):
    def setUp(self) -> None:
        self.project = sample_project.SampleProject()
        self.project.create_capture()
        assert self.project.cprops

    @skip_no_aud
    def testSoundFilePath(self) -> None:
        props = self.project.cprops
        self.project.set_capture_sound()

        self.assertEqual(props.sound_file_extension, 'ogg')
        self.assertEqual(props.sound_file_basename, 'en_male_electricity')
        self.assertIn('data', props.sound_file_folder)
        self.assertTrue(props.is_sound_format_supported())

        newName = self.project.cprops.get_sound_name_with_new_extension("wav")
        self.assertEqual(newName, 'en_male_electricity.wav')


if __name__ == '__main__':
    unittest.main()
