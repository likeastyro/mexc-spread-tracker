"""Support flat imports inside generated protobuf modules.

The MEXC protobuf files generate imports such as `import Foo_pb2`
instead of package-qualified imports. Adding this directory to
`sys.path` keeps those generated modules importable without patching
the generated code.
"""
import os
import sys

sys.path.insert(0, os.path.dirname(__file__))
