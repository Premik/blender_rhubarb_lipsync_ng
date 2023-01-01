from functools import cached_property
from pathlib import Path
import unittest
from  rhubarb_lipsync.rhubarb.process_sound_file import RhubarbCommandWrapper, RhubarbParser
import platform
import sys
import inspect
from time import sleep


def wait_unitl_finished(r:RhubarbCommandWrapper):
    assert r.was_started
    for i in range(0,100):
        if r.has_finished:
            return        
        sleep(0.1)
        r.handle_process_output()
    assert False, "Seems the process in hanging up"

class MockProcess:

    def __init__(self) -> None:
        self.python=sys.executable

    def cmd_args(self, python_code:str)->list[str]:
        # https://stackoverflow.com/questions/11157043/does-python-have-a-built-in-function-for-unindenting-a-multiline-string#
        #print(f"'{inspect.cleandoc(python_code)}'")
        return [self.python, "-c", inspect.cleandoc(python_code)]

    
    def version(self):
        return self.cmd_args("""\
            print()
            print('MOCK Rhubarb Lip Sync version 12.34.56')
        """)
        

    

class RhubarbCommandWrapperMockTest(unittest.TestCase):

    mock_proc = MockProcess()

    def testVerifyError(self):
        rcw=RhubarbCommandWrapper(Path("notExistingFile"))
        errors=rcw.errors()
        assert errors
        assert "doesn't exist" in errors

    def testVersion(self):
        mock=RhubarbCommandWrapperMockTest.mock_proc
        #rcw=RhubarbCommandWrapper(mock.version())
        #from subprocess import Popen, PIPE
        #p=Popen(mock.version(), stdout=PIPE, stderr=PIPE, universal_newlines=True)
        #print(list(p.stdout))
        #print(stdout)
        #print(stderr)
        #print(p.returncode)
        
        #print(rcw.get_version())

class RhubarbCommandWrapperTest(unittest.TestCase):

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
        rcw=RhubarbCommandWrapper(self.executable_path)
        self.assertEquals(rcw.get_version(), "1.13.0")
        self.assertEquals(rcw.get_version(), "1.13.0")
        
        
        #self.assertEqual(len(s.fullyMatchingParts()), 2)

class RhubarbParserTest(unittest.TestCase):
        
    def testVersion(self):
        self.assertFalse(RhubarbParser.parse_version_info(""))
        self.assertFalse(RhubarbParser.parse_version_info("invalid"))
        self.assertEquals(RhubarbParser.parse_version_info("\nRhubarb Lip Sync version 01.2.3 \n"), "01.2.3")



if __name__ == '__main__':
    #unittest.main(RhubarbParserTest())
    #unittest.main(RhubarbCommandWrapperTest())
    unittest.main()
    