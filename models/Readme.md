# Civic AI Models

This directory contains the trained AI models used by the Civic Issue Reporting System.

> **Important:** Model files are **not stored directly in the Git repository**. They are distributed through the project's GitHub Releases to keep the repository lightweight.

## Directory Structure

After setup, this directory should look like:

```text
models/
└── civic_clip/
    ├── config.json
    ├── model.safetensors
    ├── preprocessor_config.json
    ├── tokenizer_config.json
    ├── tokenizer.json
    ├── vocab.json
    ├── merges.txt
    └── ...
```

The exact files may vary depending on the model release.

---

## Quick Setup

### 1. Open the GitHub Releases page

Go to the project's **Releases** page:

**[[https://github.com/Unknownerror-404/The_query_solver/releases]]**

Download the latest model release.

For example:

```text
Civic AI Model v1.0.0
```

GitHub Releases provide downloadable release assets separately from the source code.

---

### 2. Download the model archive

Download the model archive from the release assets.

It will typically look something like:

```text
civic_clip.zip
```

or:

```text
civic_clip_v1.0.0.zip
```

**Do not download the repository's "Source code (zip)" for the model.**

You need the **model asset** attached to the release.

---

### 3. Extract the archive

Extract the downloaded ZIP file.

You should see the model files inside.

For example:

```text
civic_clip/
├── config.json
├── model.safetensors
├── preprocessor_config.json
├── tokenizer_config.json
├── tokenizer.json
├── vocab.json
└── merges.txt
```

---

### 4. Copy the model into `models/`

Copy the entire `civic_clip` folder into the project's `models/` directory.

The final structure should be:

```text
your-project/
├── AI_model.py
├── app_fastapi.py
├── community.py
├── storage.py
├── models/
│   ├── README.md
│   └── civic_clip/
│       ├── config.json
│       ├── model.safetensors
│       ├── preprocessor_config.json
│       ├── tokenizer_config.json
│       ├── tokenizer.json
│       ├── vocab.json
│       └── merges.txt
└── ...
```

### Avoid an extra nested folder

**Incorrect:**

```text
models/
└── civic_clip/
    └── civic_clip/
        ├── config.json
        └── model.safetensors
```

**Correct:**

```text
models/
└── civic_clip/
    ├── config.json
    └── model.safetensors
```

The directory containing `config.json` and the model weights should be the directory loaded by the application.

---

## 5. Start the application

Once the model has been copied into place, start the backend normally.

The application will load the fine-tuned model from:

```text
models/civic_clip/
```

If your installation uses a custom model location, you can override the default path with:

```text
CIVIC_CLIP_MODEL_DIR
```

For example, on Windows PowerShell:

```powershell
$env:CIVIC_CLIP_MODEL_DIR="C:\path\to\your-project\models\civic_clip"
```

On Linux/macOS:

```bash
export CIVIC_CLIP_MODEL_DIR="/path/to/your-project/models/civic_clip"
```

---

## Troubleshooting

### `Model not found`

Check that this directory exists:

```text
models/civic_clip/
```

and that it contains:

```text
config.json
```

and the model weight file, such as:

```text
model.safetensors
```

---

### The application cannot load the model

Make sure you copied the **contents of the model release**, rather than accidentally copying the ZIP file itself.

For example:

**Incorrect:**

```text
models/
└── civic_clip.zip
```

**Correct:**

```text
models/
└── civic_clip/
    ├── config.json
    ├── model.safetensors
    └── ...
```

---

### I downloaded the wrong file

Do not use:

```text
Source code (zip)
Source code (tar.gz)
```

Those are GitHub-generated source archives.

Instead, download the model archive listed under the release's **Assets** section.

---

## Updating the Model

When a newer model is released:

1. Open the project's GitHub Releases page.
2. Download the latest model archive.
3. Remove or rename the existing `models/civic_clip/` directory.
4. Extract the new model.
5. Copy the new `civic_clip/` directory into `models/`.
6. Restart the application.

For example:

```text
models/
└── civic_clip/
    ├── config.json
    ├── model.safetensors
    └── ...
```

The application will then use the new model.

---

## Model Version

The model currently expected by this project is:

```text
Civic CLIP
```

Model version:

```text
v1.0.0
```

If the model version changes, refer to the corresponding GitHub Release for the correct files.

---

## Why are the model files not included in Git?

Trained model weights can be substantially larger than normal source-code files. Keeping them in Git would unnecessarily increase repository size.

Instead:

```text
Git Repository
      │
      ├── Source code
      ├── Configuration
      ├── Documentation
      │
      └── models/
          └── README.md
                  │
                  ▼
          GitHub Release
                  │
                  ▼
          Trained Model
```

This keeps the source repository lightweight while still giving users a simple installation process.

---

## TL;DR

```text
1. Open GitHub → Releases
2. Download the latest Civic CLIP model ZIP
3. Extract it
4. Copy civic_clip/ into models/
5. Make sure config.json is directly inside models/civic_clip/
6. Start the application
```

Final structure:

```text
models/
└── civic_clip/
    ├── config.json
    ├── model.safetensors
    └── ...
```

That's it.
