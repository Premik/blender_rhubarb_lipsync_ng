from functools import cached_property
from pathlib import Path
import unittest
from  rhubarb_lipsync.rhubarb.process_sound_file import RhubarbCommandWrapper, RhubarbParser

import platform
import sys
import inspect
from time import sleep
#import tests.test_data
import test_data

def wait_until_finished(r:RhubarbCommandWrapper):
    assert r.was_started
    for i in range(0,100):
        if r.has_finished:
            return        
        sleep(0.01)
        print(f"{r.lipsync_check_progress()}%")
        #print(r.stderr)
        #print(r.stdout)
    assert False, "Seems the process in hanging up"

class RhubarbCommandWrapperTest(unittest.TestCase):

    def setUp(self):
        self.wrapper=RhubarbCommandWrapper(self.executable_path)

    @staticmethod
    def executable_default_basename()->str:
        return "rhubarb.exe" if platform.system() == "Windows" else "rhubarb"

    @cached_property
    def project_dir(self) -> Path:
        return Path(__file__).parents[1]

    @cached_property
    def executable_path(self) -> Path:        
        return self.project_dir / "bin" / RhubarbCommandWrapperTest.executable_default_basename()

    def testVersion(self):
        self.assertEqual(self.wrapper.get_version(), "1.13.0")
        self.assertEqual(self.wrapper.get_version(), "1.13.0")

    def testLipsync_cs(self):
        p = test_data.snd_cs_female_o_a["snd_file_path"]
        self.wrapper.lipsync_start(p)
        wait_until_finished(self.wrapper)
        print(RhubarbParser.parse_lipsync_json(self.wrapper.stdout))
        

        
        
        #self.assertEqual(len(s.fullyMatchingParts()), 2)

class RhubarbParserTest(unittest.TestCase):
        
    def testVersion(self):
        self.assertFalse(RhubarbParser.parse_version_info(""))
        self.assertFalse(RhubarbParser.parse_version_info("invalid"))
        self.assertEqual(RhubarbParser.parse_version_info("\nRhubarb Lip Sync version 01.2.3 \n"), "01.2.3")

    def testStatusLine(self):
        failed='''{ "type": "failure", "reason": "Error processing file Foo\\nBar\\n" }'''
        sts=RhubarbParser.parse_status_infos(failed)
        assert len(sts)==1
        st=sts[0]
        assert st["type"] == "failure"



if __name__ == '__main__':
    #unittest.main(RhubarbParserTest())
    #unittest.main(RhubarbCommandWrapperTest())
    unittest.main(RhubarbCommandWrapperTest())
    #unittest.main()

    