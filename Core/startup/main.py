import sys

from Core.cli.arguments import parse_arguments
from Core.cli.instance import InstanceDriver

def main() -> int:
    if sys.argv[1:2] == ['--diagnose-network']:
        from Core.cli.network_probe import run
        return run(sys.argv[2:])
    if sys.argv[1:2] == ['--verify-release-ui']:
        from Core.presentation.runtime.release_check import run
        return run(sys.argv[2:])
    if sys.argv[1:] == ['--verify-embedded-resources']:
        import json
        from Core.resources.runtime import verify_embedded_resources
        print(json.dumps(verify_embedded_resources()))
        return 0
    from Core.updates.resume import initialize
    request = parse_arguments(initialize(sys.argv[1:]))
    instance = InstanceDriver()
    try:
        if not instance.primary:
            response = instance.forward(request)
            sys.stdout.write(response.stdout)
            sys.stderr.write(response.stderr)
            return response.code
        from Core.startup.entry import main as launch
        return launch(request, instance)
    finally:
        instance.close()


if __name__ == "__main__":
    raise SystemExit(main())
