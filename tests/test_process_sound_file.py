import unittest
from rhubarb.process_sound_file import RhubarbCommandWrapper

class RhubarbCommandWrapperTest(unittest.TestCase):
    
    def testVerify(self):
        rcw=RhubarbCommandWrapper("notExistingFile")
        errors=rcw.verify()
        assert errors
        assert "doesn't exists" in errors


        
        #self.assertEqual(len(s.fullyMatchingParts()), 2)



if __name__ == '__main__':
    unittest.main()
    