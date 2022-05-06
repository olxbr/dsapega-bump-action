[![Tests](https://github.com/olxbr/blackbox-action/actions/workflows/test.yml/badge.svg?branch=main)](https://github.com/olxbr/blackbox-action/actions/workflows/test.yml)
# blackbox-action

Black Box is the popularly known name of a voice and data recording device found on aircraft.

The idea is to use this Action in all org repositories in order to collect information.

```text
In the aircraft context, "Black Box" is an outdated name which has become a misnomer,
they are now required to be painted bright orange, to aid in their recovery after accidents.
```

## Usage
We recommend using it in a specific Workflow.

```yaml
# .github/workflows/blackbox-workflow.yml
jobs:
    run-blackbox-action:
        runs-on: [self-hosted, ...]
        steps:
            - uses: actions/checkout@v3

            - id: blackbox
              uses: olxbr/blackbox-action@v1
              with:
                config: ${{ secrets.BLACK_BOX_CONFIG }}
```