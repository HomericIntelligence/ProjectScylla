# T0: Prompts

System prompt ablation tier with 24 sub-tests testing different prompt configurations.

## Sub-test Categories

### Core Configurations (4)

- `00-empty/` - No system prompt (absolute baseline)
- `01-vanilla/` - Default tool system prompt only
- `02-critical-only/` - B02 safety rules only (~55 lines)
- `03-full/` - All 18 blocks (1787 lines)

### Preset Variations (2)

- `04-minimal/` - B02, B07, B18 (~260 lines)
- `05-core-seven/` - B02, B05, B07, B09, B12, B16, B18 (~400 lines)

### Individual Blocks (18)

- `06-B01/` through `23-B18/` - Each CLAUDE.md block tested individually

## Purpose

This tier measures the impact of different system prompt configurations on agent performance.
The goal is to identify which prompt components are essential vs. optional for different task types.

## Metrics Captured

- Pass-Rate across prompt configurations
- Token usage differences
- Cost-of-Pass for each configuration
- Consistency across runs
