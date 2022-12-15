import unittest
import process_sound_file 

class RhubarbCommandWrapperTest(unittest.TestCase):
    
    def testSetup(self):
        rcw=process_sound_file.RhubarbCommandWrapper("notExistingFile")

        
        #self.assertEqual(len(s.fullyMatchingParts()), 2)



if __name__ == '__main__':
    unittest.main()
    