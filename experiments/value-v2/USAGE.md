# Run a local document task

Python 3 and a **local** OpenAI-compatible chat endpoint with native tool calls
are required. This package does not download or start a model automatically
when using `agent.py`. Only loopback HTTP endpoints are accepted. An endpoint
must support the tool schemas and `tool_choice=required`; arbitrary servers
are not qualified by these results.

## Use the public example without a model

From this directory:

```bash
python3 client/render_report.py \
  --receipt evidence/motif-repair-recheck-v4/known-target-020.json \
  --output /tmp/motif-example-report.md
```

Choose an output file that does not already exist. Read the answer together
with the actual source passage. A valid report is not an automatic correctness
certificate. Examples of complete but wrong answers are included in `examples/`.

## Use your own Markdown files

Put one project's UTF-8 `.md` files directly in a directory: at most 256 files,
32 KiB each. The filename stem is the document ID. Subdirectories, symlinks,
PDF, and Word files are not supported. Create the subject index:

```bash
python3 client/index_documents.py \
  --documents /absolute/path/to/documents \
  --subject my-project --alias 'My project'
```

An existing index is not overwritten. It binds every document to its project
and SHA-256. If source content changes, make a new document snapshot and index.
Multiple projects require a manually reviewed per-document subject map.

With your native-tool endpoint already running on loopback:

```bash
python3 client/agent.py \
  --endpoint http://127.0.0.1:8825 \
  --model-name YOUR_LOCAL_MODEL_NAME \
  --documents /absolute/path/to/documents \
  --subject my-project \
  --task 'My project의 확인 코드를 해당 문서를 인용해서 알려줘.' \
  --output /tmp/my-document-receipt.json
python3 client/render_report.py \
  --receipt /tmp/my-document-receipt.json \
  --output /tmp/my-document-report.md
```

For public fixture exploration, use `workflows/known-target-documents`, subject
`heldout-020`, and the question in `workflows/cases.json`. These are known cases,
not fresh independent tests. Public redacted fixture hashes are in
`workflows/public-freeze.json`.

## Boundaries

Search and read stay within the chosen subject. Unspecified subjects in an
indexed folder are rejected before calling the model. The model selects source
line spans and the application copies the actual text. Up to four passages,
16 lines and 4,000 characters per passage, are allowed. A claim can still be
unsupported by the passage it cites; review the interpretation separately.

The default limit is eight tool steps and 300 seconds, with at most 90 seconds
per model request and 640 characters in the final answer. The last step only
allows reporting. Two report-correction opportunities are allowed; an identical
repeated call still stops. This does not guarantee successful recovery or
semantic completeness.

The model has search, read, limited arithmetic, and report tools. It has no file
write, shell, web, or messaging tool. The caller explicitly saves output files.
Legacy unindexed folders can be read, but their receipt says
`subject_bound: false`.

## Exact experimental runtimes

`client/run_local.py` is the optional one-task launcher for an already prepared
Spark installation. It verifies model identity, starts its owned loopback
server, and stops it after the task. Fill in the example configuration with
your existing runtime/model/binding paths. No configuration here supplies the
runtime or weights. Motif draft 1 also requires a correctly linked sidecar.

The recorded runs used the pinned public runtime, existing tokenizer/MTP work,
and opt-in native parsers. See [parser instructions](runtime/agent-parsers/README.md).
The small Q8 reference patch is a separate experiment; do not stack it with the
full MTP runtime patch as though the two patches were interchangeable.

Run model-free client checks from the `client` directory:

```bash
python3 -m unittest -v test_agent
```
