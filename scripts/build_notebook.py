"""
Convierte un "recipe" de celdas (lista de dicts) en un .ipynb real,
lo ejecuta con el kernel del venv del proyecto y guarda outputs.

Uso: cada notebook fuente vive en scripts/recipes/NN_nombre.py y define
una variable CELLS = [{"type": "markdown"|"code", "source": "..."}, ...]

    python scripts/build_notebook.py scripts/recipes/01_fundamentos.py notebooks/01_fundamentos_python_datos.ipynb
"""
import importlib.util
import sys
from pathlib import Path

import nbformat
from nbformat.v4 import new_notebook, new_markdown_cell, new_code_cell
from nbclient import NotebookClient


def load_recipe(path):
    spec = importlib.util.spec_from_file_location("recipe", path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod.CELLS


def build(recipe_path, out_path):
    cells_spec = load_recipe(recipe_path)
    nb = new_notebook()
    nb.metadata = {
        "kernelspec": {"display_name": "Python 3", "language": "python", "name": "python3"},
        "language_info": {"name": "python", "version": "3.11"},
    }
    for c in cells_spec:
        if c["type"] == "markdown":
            nb.cells.append(new_markdown_cell(c["source"].strip("\n")))
        else:
            nb.cells.append(new_code_cell(c["source"].strip("\n")))

    client = NotebookClient(nb, timeout=120, kernel_name="python3")
    client.execute(cwd=str(Path(out_path).resolve().parent.parent))

    out_path = Path(out_path)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with open(out_path, "w", encoding="utf-8") as f:
        nbformat.write(nb, f)
    print(f"OK -> {out_path} ({len(nb.cells)} celdas)")


if __name__ == "__main__":
    build(sys.argv[1], sys.argv[2])
