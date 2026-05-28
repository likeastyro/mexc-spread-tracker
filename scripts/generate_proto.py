from __future__ import annotations

from pathlib import Path
import sys

from grpc_tools import protoc


def main() -> int:
    repo_root = Path(__file__).resolve().parent.parent
    proto_dir = repo_root / "parser" / "proto"
    proto_files = sorted(str(path) for path in proto_dir.glob("*.proto"))

    if not proto_files:
        print("No .proto files found in parser/proto", file=sys.stderr)
        return 1

    result = protoc.main(
        [
            "grpc_tools.protoc",
            f"-I{proto_dir}",
            f"--python_out={proto_dir}",
            *proto_files,
        ]
    )
    if result != 0:
        print("protobuf generation failed", file=sys.stderr)
        return result

    print(f"Generated {len(proto_files)} protobuf modules in {proto_dir}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
