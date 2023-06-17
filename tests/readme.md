# Tests
Some tests are more like integration tests where they use the blender-as-python module. Some of these test would make other tests to fail since blender-module has a global state. 

To run the tests active conde env. The `pytest-xdist` and `pytest-forked` plugins are needed. Then run:

```sh
pytest -n auto --forked
```