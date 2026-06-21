import os
import re
from flask import Flask, request, jsonify, render_template
from supabase import create_client, Client

app = Flask(__name__)

SUPABASE_URL = os.environ["SUPABASE_URL"]
SUPABASE_KEY = os.environ["SUPABASE_KEY"]
supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)


@app.route("/")
def index():
    projects = supabase.table("projects").select("*").order("created_at", desc=True).execute().data
    tasks = supabase.table("tasks").select("*").execute().data

    tasks_by_project = {}
    for t in tasks:
        tasks_by_project.setdefault(t["project_id"], []).append(t)

    for p in projects:
        p_tasks = tasks_by_project.get(p["id"], [])

        # progresso conta só tasks de verdade (títulos não entram na conta)
        tasks_reais = [t for t in p_tasks if not t.get("is_titulo")]
        total = len(tasks_reais)
        done = sum(1 for t in tasks_reais if t["done"])
        p["progresso"] = f"{done}/{total}" if total else "0/0"
        p["progresso_pct"] = int((done / total) * 100) if total else 0

        # lista linear única, ordenada por "ordem" (fallback created_at)
        p["itens"] = sorted(p_tasks, key=lambda x: (x.get("ordem") or 0, x["created_at"]))

    freelance = [p for p in projects if p["tipo"] == "freelance"]
    pessoal = [p for p in projects if p["tipo"] == "pessoal"]

    return render_template("index.html", freelance=freelance, pessoal=pessoal)


@app.route("/projects", methods=["POST"])
def create_project():
    data = request.json
    nome = (data.get("nome") or "").strip()
    objetivo = (data.get("objetivo") or "").strip()
    tipo = data.get("tipo", "pessoal")

    if not nome:
        return jsonify({"error": "nome é obrigatório"}), 400
    if tipo not in ("freelance", "pessoal"):
        return jsonify({"error": "tipo inválido"}), 400

    result = supabase.table("projects").insert({
        "nome": nome,
        "objetivo": objetivo,
        "tipo": tipo
    }).execute()

    return jsonify(result.data[0]), 201


@app.route("/projects/<project_id>", methods=["DELETE"])
def delete_project(project_id):
    supabase.table("projects").delete().eq("id", project_id).execute()
    return "", 204


@app.route("/projects/<project_id>/titulo", methods=["POST"])
def create_titulo(project_id):
    """Cria um item-título solto na lista, sem nenhuma task associada ainda."""
    data = request.json
    nome = (data.get("nome") or "").strip()

    if not nome:
        return jsonify({"error": "nome é obrigatório"}), 400

    # entra no fim da lista: pega a maior ordem atual do projeto + 1
    existentes = supabase.table("tasks").select("ordem").eq("project_id", project_id).execute().data
    maior_ordem = max([t.get("ordem") or 0 for t in existentes], default=-1)

    result = supabase.table("tasks").insert({
        "project_id": project_id,
        "descricao": nome,
        "is_titulo": True,
        "ordem": maior_ordem + 1
    }).execute()

    return jsonify(result.data[0]), 201


@app.route("/projects/<project_id>/tasks", methods=["POST"])
def create_task(project_id):
    data = request.json
    raw = data.get("descricao") or ""

    partes = re.split(r"[,\n]", raw)
    descricoes = [p.strip() for p in partes if p.strip()]

    if not descricoes:
        return jsonify({"error": "descricao é obrigatória"}), 400

    existentes = supabase.table("tasks").select("ordem").eq("project_id", project_id).execute().data
    maior_ordem = max([t.get("ordem") or 0 for t in existentes], default=-1)

    novas_tasks = []
    for i, d in enumerate(descricoes):
        novas_tasks.append({
            "project_id": project_id,
            "descricao": d,
            "ordem": maior_ordem + 1 + i
        })

    result = supabase.table("tasks").insert(novas_tasks).execute()

    return jsonify(result.data), 201


@app.route("/tasks/<task_id>", methods=["PATCH"])
def toggle_task(task_id):
    data = request.json
    done = data.get("done")

    if done is None:
        return jsonify({"error": "done é obrigatório"}), 400

    result = supabase.table("tasks").update({"done": done}).eq("id", task_id).execute()
    return jsonify(result.data[0])


@app.route("/tasks/<task_id>", methods=["DELETE"])
def delete_task(task_id):
    supabase.table("tasks").delete().eq("id", task_id).execute()
    return "", 204


@app.route("/tasks/reorder", methods=["POST"])
def reorder_tasks():
    """
    Recebe a lista completa de itens (tasks + títulos) de um projeto,
    já na ordem visual final após um drag-and-drop.

    Body esperado:
    {
      "items": ["task-uuid-1", "titulo-uuid-2", "task-uuid-3", ...]
    }

    Cada item recebe sua posição (índice na lista) como nova "ordem".
    Pertencimento a uma seção é sempre derivado da posição no render,
    não precisa ser armazenado.
    """
    data = request.json
    items = data.get("items") or []

    if not items:
        return jsonify({"error": "items é obrigatório"}), 400

    for posicao, item_id in enumerate(items):
        if not item_id:
            continue
        supabase.table("tasks").update({"ordem": posicao}).eq("id", item_id).execute()

    return jsonify({"ok": True}), 200


if __name__ == "__main__":
    app.run(debug=True, port=5000)