import unittest
from  rhubarb_lipsync.rhubarb.process_sound_file import RhubarbCommandWrapper

class RhubarbCommandWrapperTest(unittest.TestCase):
    
    def testVerify(self):
        rcw=RhubarbCommandWrapper("notExistingFile")
        errors=rcw.verify()
        assert errors
        assert "doesn't exists" in errors

    def testVersion(self):
       print(__file__)


        
        #self.assertEqual(len(s.fullyMatchingParts()), 2)



if __name__ == '__main__':
    unittest.main()
    