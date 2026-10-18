---
source: https://docs.getsemantica.ai/installation
title: Installation - Semantica
---

# Installation - Semantica

**Available on PyPI**: `pip install semantica` and you’re ready.

Python 3.10 or higher is required (3.10–3.13 are supported). Python 3.11+ is recommended.

##  System Requirements

| Component | Minimum | Recommended |
| --- | --- | --- |
| Python | 3.10 | 3.11+ |
| OS | Windows / Linux / Mac | Linux / Mac |
| RAM | 4 GB | 16 GB+ |
| Storage | 2 GB | 20 GB+ (models and data) |

##  Basic Installation

```
pip install semantica
```

With all optional dependencies:

```
pip install semantica[all]
```

###  Verify

```
python -c "import semantica; print(semantica.__version__)"
```

##  Virtual Environment (Recommended)

* venv
* conda

```
python -m venv venv
source venv/bin/activate   # Linux / Mac
venv\Scripts\activate      # Windows
pip install semantica
```

```
conda create -n semantica python=3.11
conda activate semantica
pip install semantica
```

##  Optional Dependencies

Install only what you need:

* GPU
* Visualization
* LLM Providers
* Cloud

```
pip install semantica[gpu]
```

Includes PyTorch with CUDA, FAISS GPU, and CuPy.

```
pip install semantica[viz]
```

Includes PyVis, Graphviz, and UMAP.

```
pip install semantica[llm-all]       # all providers
pip install semantica[llm-openai]    # OpenAI
pip install semantica[llm-anthropic] # Anthropic
pip install semantica[llm-gemini]    # Google Gemini
pip install semantica[llm-groq]      # Groq
pip install semantica[llm-ollama]    # Ollama (local)
```

```
pip install semantica[cloud]
```

Includes AWS S3, Azure Blob, and Google Cloud Storage.

##  Install from Source

For the latest development version or to contribute:

```
git clone https://github.com/semantica-agi/semantica.git
cd semantica

pip install -e .         # core only
pip install -e ".[all]"  # all extras
pip install -e . --group dev  # dev tools (pytest, black, etc.); needs pip 25.1+, or use `uv sync`
```

Install directly from the main branch if the PyPI release has issues:

```
pip install git+https://github.com/semantica-agi/semantica.git@main
```

##  Troubleshooting

ModuleNotFoundError: No module named 'semantica'

Make sure you’re in the right virtual environment:

```
pip list | grep semantica
pip install --upgrade semantica
```

Installation fails with dependency errors

```
pip install --upgrade pip
pip install build wheel
pip install semantica --no-deps  # install core first, then add extras
```

GPU dependencies fail to install

Install CPU-only first, then layer in GPU support:

```
pip install semantica
pip install semantica[gpu]
```

Permission denied

```
pip install --user semantica  # or use a virtual environment
```

Windows [all] install fails

Fixed in **v0.5.0**. Upgrade to the latest release:

```
pip install --upgrade semantica
```

Windows PyTorch DLL errors on startup

Install the [Microsoft Visual C++ Redistributable](https://aka.ms/vs/17/release/vc_redist.x64.exe). This is a Windows system dependency, not a Semantica bug.

##  Next Steps

* [Getting Started](/getting-started): understand what Semantica does before you build.
* [Build the Pipeline](/quickstart): follow the end-to-end workflow with code.
* [Browse Examples](/cookbook): see notebook examples organized by use case.
