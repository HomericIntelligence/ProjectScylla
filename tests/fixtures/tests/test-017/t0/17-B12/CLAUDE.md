### Tool Use Optimization

Efficient tool use reduces latency and token consumption. Follow these patterns:

#### Parallel Tool Calls

**DO**: Make independent tool calls in parallel:

```python
# ✅ GOOD - Parallel reads
read_file_1 = Read("/path/to/file1.mojo")
read_file_2 = Read("/path/to/file2.mojo")
read_file_3 = Read("/path/to/file3.mojo")
# All three reads happen concurrently

# ❌ BAD - Sequential reads
read_file_1 = Read("/path/to/file1.mojo")
# Wait for result...
read_file_2 = Read("/path/to/file2.mojo")
# Wait for result...
read_file_3 = Read("/path/to/file3.mojo")
```

**DO**: Group related grep searches:

```python
# ✅ GOOD - Parallel greps
grep_functions = Grep(pattern="fn .*", glob="*.mojo")
grep_structs = Grep(pattern="struct .*", glob="*.mojo")
grep_tests = Grep(pattern="test_.*", glob="test_*.mojo")
# All searches run in parallel

# ❌ BAD - Sequential greps with waiting
grep_functions = Grep(pattern="fn .*", glob="*.mojo")
# Process results, then...
grep_structs = Grep(pattern="struct .*", glob="*.mojo")
```

#### Bash Command Patterns

**DO**: Use absolute paths in bash commands (cwd resets between calls):

```bash
# ✅ GOOD - Absolute paths
cd /home/user/ProjectOdyssey && pixi run mojo test tests/shared/core/test_tensor.mojo

# ❌ BAD - Relative paths (cwd not guaranteed)
cd ProjectOdyssey && pixi run mojo test tests/shared/core/test_tensor.mojo
```

**DO**: Combine related commands with && for atomicity:

```bash
# ✅ GOOD - Atomic operation
cd /home/user/ProjectOdyssey && \
  git checkout -b 2549-claude-md && \
  git add CLAUDE.md && \
  git commit -m "docs: add Claude 4 optimization guidance"

# ❌ BAD - Multiple separate bash calls (cwd resets)
cd /home/user/ProjectOdyssey
git checkout -b 2549-claude-md  # Might run in different directory!
git add CLAUDE.md
```

**DO**: Capture output explicitly when needed:

```bash
# ✅ GOOD - Capture and parse output
cd /home/user/ProjectOdyssey && \
  pixi run mojo test tests/ 2>&1 | tee test_output.log && \
  grep -c PASSED test_output.log

# ❌ BAD - Output lost between calls
cd /home/user/ProjectOdyssey && pixi run mojo test tests/
# Output is gone, can't analyze it
```

#### Tool Selection

Use the right tool for the job:

| Task | Tool | Rationale |
|------|------|-----------|
| Read file | Read | Fast, includes lines |
| Search pattern | Grep | Optimized regex |
| Find files | Glob | Fast discovery |
| Run commands | Bash | Execute shell |
| Edit lines | Edit | Precise replace |
| Write file | Write | Create/overwrite |

**DO**: Use the most specific tool:

```python
# ✅ GOOD - Use Glob to find files, then Read them
files = Glob(pattern="**/test_*.mojo")
for file in files:
    content = Read(file)

# ❌ BAD - Use Bash for file discovery
result = Bash("find . -name 'test_*.mojo'")
# Now have to parse shell output
```
