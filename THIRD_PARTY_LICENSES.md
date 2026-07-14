# Third-Party Licenses

enough itself is released under the Apache License, Version 2.0. See
[LICENSE](LICENSE) at the repository root.

This file documents the licensing of

1. third-party code **bundled** in this repository, and
2. third-party projects that enough **depends on at runtime** (installed
   by the user via Homebrew, uv, or `bootstrap.sh`, not included here).

We're not lawyers. For anything commercial-facing, a real attorney should
double-check the obligations. Links below point to each project's
canonical license; that text governs in the case of any discrepancy
with this summary.

---

## Bundled code

Two third-party source files ship in this repository:

### htmx

`enough/static/htmx.min.js` is a copy of **htmx** (<https://htmx.org>),
distributed under the BSD 2-Clause License, reproduced below verbatim.

```
BSD 2-Clause License

Copyright (c) 2020, Big Sky Software
All rights reserved.

Redistribution and use in source and binary forms, with or without
modification, are permitted provided that the following conditions are
met:

1. Redistributions of source code must retain the above copyright
   notice, this list of conditions and the following disclaimer.

2. Redistributions in binary form must reproduce the above copyright
   notice, this list of conditions and the following disclaimer in the
   documentation and/or other materials provided with the distribution.

THIS SOFTWARE IS PROVIDED BY THE COPYRIGHT HOLDERS AND CONTRIBUTORS
"AS IS" AND ANY EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT
LIMITED TO, THE IMPLIED WARRANTIES OF MERCHANTABILITY AND FITNESS FOR
A PARTICULAR PURPOSE ARE DISCLAIMED. IN NO EVENT SHALL THE COPYRIGHT
HOLDER OR CONTRIBUTORS BE LIABLE FOR ANY DIRECT, INDIRECT, INCIDENTAL,
SPECIAL, EXEMPLARY, OR CONSEQUENTIAL DAMAGES (INCLUDING, BUT NOT
LIMITED TO, PROCUREMENT OF SUBSTITUTE GOODS OR SERVICES; LOSS OF USE,
DATA, OR PROFITS; OR BUSINESS INTERRUPTION) HOWEVER CAUSED AND ON ANY
THEORY OF LIABILITY, WHETHER IN CONTRACT, STRICT LIABILITY, OR TORT
(INCLUDING NEGLIGENCE OR OTHERWISE) ARISING OUT OF THE USE OF THIS
SOFTWARE, EVEN IF ADVISED OF THE POSSIBILITY OF SUCH DAMAGE.
```

### Mermaid

`enough/static/mermaid.min.js` is a copy of **Mermaid**
(<https://mermaid.js.org>, <https://github.com/mermaid-js/mermaid>), the
minified UMD build of Mermaid v11, distributed under the MIT License,
reproduced below verbatim. It renders `.merirmaid` diagrams client-side
(vendored, no CDN); the `girraph-merirmaid` skill also ships excerpts of
Mermaid's MIT-licensed syntax documentation under
`defaults/skills/girraph-merirmaid/references/`.

```
The MIT License (MIT)

Copyright (c) 2014 - 2022 Knut Sveidqvist

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all
copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
SOFTWARE.
```

---

## Runtime dependencies

These projects are installed on the user's machine by `bootstrap.sh`,
`uv`, or Homebrew — they are **not redistributed** as part of this
repository. Each is governed by its own license; consult the linked
project for authoritative text.

### Inference runtime

| Project | License | Role | Source |
|---|---|---|---|
| ggml | MIT | Tensor library (shared C++ core for llama.cpp + whisper.cpp) | <https://github.com/ggml-org/ggml> |
| llama.cpp | MIT | Local LLM inference (chat model) | <https://github.com/ggml-org/llama.cpp> |
| whisper.cpp | MIT | Local speech-to-text (voice input) | <https://github.com/ggml-org/whisper.cpp> |

All three by Georgi Gerganov and contributors.

### Python server stack

| Project | License | Role | Source |
|---|---|---|---|
| Python | PSF License | Language runtime | <https://www.python.org> |
| FastAPI | MIT | HTTP server framework | <https://github.com/fastapi/fastapi> |
| Starlette | BSD-3-Clause | ASGI toolkit under FastAPI | <https://github.com/encode/starlette> |
| uvicorn | BSD-3-Clause | ASGI server | <https://github.com/encode/uvicorn> |
| httpx | BSD-3-Clause | Async HTTP client (llama-server comms) | <https://github.com/encode/httpx> |
| sse-starlette | BSD-3-Clause | Server-Sent Events for FastAPI | <https://github.com/sysid/sse-starlette> |
| python-multipart | Apache-2.0 | Multipart form parsing | <https://github.com/Kludex/python-multipart> |
| pydantic | MIT | Data models under FastAPI | <https://github.com/pydantic/pydantic> |

### Translation runtime

The `translator` skill (default-installed) uses these Python libraries
to run the MADLAD-400 translation model offline:

| Project | License | Role | Source |
|---|---|---|---|
| CTranslate2 | MIT | Fast inference engine for transformer models (translation) | <https://github.com/OpenNMT/CTranslate2> |
| SentencePiece | Apache-2.0 | Subword tokenizer for the MADLAD model | <https://github.com/google/sentencepiece> |
| huggingface_hub | Apache-2.0 | Downloads model weights from Hugging Face on first use | <https://github.com/huggingface/huggingface_hub> |

### Front-end

| Project | License | Role | Source |
|---|---|---|---|
| htmx | BSD-2-Clause | Progressive-enhancement frontend (see bundled copy above) | <https://htmx.org> |
| Mermaid | MIT | Client-side diagram rendering for `.merirmaid` files (see bundled copy above) | <https://mermaid.js.org> |

### Tooling

| Project | License | Role | Source |
|---|---|---|---|
| uv | Apache-2.0 OR MIT | Python environment + dependency manager | <https://github.com/astral-sh/uv> |
| Homebrew | BSD-2-Clause | macOS package manager (install path) | <https://brew.sh> |

### Optional, gated per skill

| Project | License | Role | Source |
|---|---|---|---|
| Tor | BSD-3-Clause | Anonymized web fetch for off-allowlist domains (used by the broker's `fetch_url` tool) | <https://www.torproject.org> |
| Pandoc | GPL-2.0-or-later | HTML→markdown conversion for fetched documents (invoked as an external binary; not bundled with this package) | <https://pandoc.org> |
| Harper | Apache-2.0 | Local grammar/spell checker (Automattic). Installed via `brew install harper`, which provides `harper-cli` (used by the `analyzer` skill's proofread mode) and `harper-ls` (a language server, unused by enough). Not bundled with this package. | <https://github.com/Automattic/harper> |

### System fonts (referenced, not bundled)

The default theme uses macOS system fonts (SF Mono, Georgia, the
system sans stack, Courier New). These are licensed by their respective
vendors (Apple, Microsoft, etc.) and are not redistributed by enough.

---

## Model weights

Model weights are **not bundled**. `bootstrap.sh` offers to download
your chosen subset from public Hugging Face repositories at install
time. Weights remain in `~/enough/weights/` on the user's machine and
are governed by each model's own license — check the upstream model
card before commercial use.

| Cute name | Model | Source license | Weights repo |
|---|---|---|---|
| G40-04 | Gemma 4 4B (E4B) | Gemma Terms of Use | <https://huggingface.co/ggml-org/gemma-4-E4B-it-GGUF> |
| Q35-09 | Qwen3.5-9B (MTP build) | Apache-2.0 | <https://huggingface.co/unsloth/Qwen3.5-9B-MTP-GGUF> |
| G40-26 | Gemma 4 26B A4B (MoE) | Gemma Terms of Use | <https://huggingface.co/ggml-org/gemma-4-26B-A4B-it-GGUF> |
| Q36-27 | Qwen3.6-27B (dense, MTP build) | Apache-2.0 | <https://huggingface.co/unsloth/Qwen3.6-27B-MTP-GGUF> |
| — | OpenAI Whisper `base.en` | MIT | <https://huggingface.co/ggerganov/whisper.cpp> |
| — | MADLAD-400-3B-MT (CT2) | Apache-2.0 | <https://huggingface.co/santhosh/madlad400-3b-ct2> |
| — | MADLAD-400-7B-MT (CT2, opt-in) | Apache-2.0 | <https://huggingface.co/avans06/madlad400-7b-mt-bt-ct2-int8_float16> |

Gemma weights require acceptance of Google's Gemma Terms of Use; users
download them from Hugging Face after accepting those terms on the model
card page. The OpenAI Whisper model weights are MIT-licensed; the
whisper.cpp GGML conversion ships under the same terms.

MADLAD-400 weights (3B and 7B) are released by Google under Apache 2.0
— both the upstream model and the pre-converted CTranslate2 builds
linked above. They power the `translator` skill and live at
`~/.local/share/translator/` after first download (override with the
`TRANSLATOR_HOME` env var).

---

## Skills shipped under `defaults/skills/`

Four skills ship with enough as "first-party" defaults:

| Skill | Purpose | Author |
|---|---|---|
| analyzer | Three-mode analytical workbench: summarize, proofread, decide | Graham Smith |
| memoir-dialectic | Patient multi-session memoir collaborator | Graham Smith |
| skill-scanner | Plain-English explainer and security/epistemic auditor for skill packages | Graham Smith |
| translator | Offline machine translation across ~419 languages | Graham Smith |

These are authored for the enough project and fall under the
repository's Apache 2.0 license (see [LICENSE](LICENSE)). Users may add
their own skills at `~/enough/defaults/skills/` or in any project's
`rness/skills/` directory; those skills are governed by whatever terms
the skill author chooses.

---

## Acknowledgements

Special gratitude to:

- **Georgi Gerganov** and the ggml-org community — the ggml/llama.cpp/
  whisper.cpp stack is what makes local, sovereign LLM use actually
  practical on consumer hardware. Everything else in enough is plumbing
  around what they built.
- **Carson Gross** and the htmx team — for a front-end library that
  respects how HTML was meant to work.
- **Sebastián Ramírez**, **Tom Christie**, and the encode.io collective
  — FastAPI, Starlette, uvicorn, and httpx are the quiet backbone of
  uncountable Python services, including this one.
- **Astral Software** (Charlie Marsh et al.) — `uv` replaced multiple
  tools in this project's dependency flow with one fast one.
- The **Qwen team at Alibaba** and **Google DeepMind's Gemma team** —
  for open-weights model releases that make a local-first product
  viable in the first place.
- **Automattic** and the Harper maintainers — for a local, offline,
  rule-based grammar checker that doesn't phone home and doesn't pretend
  to be an oracle. The analyzer skill's proofread mode is much sharper
  with it on PATH.
- Every maintainer of every transitively-depended project not named
  above. You are seen and appreciated.

If your project is used by enough and not credited here, please open an
issue (or a PR to this file) — we'll fix it.
