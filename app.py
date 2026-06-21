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
        p_tasks_sorted = sorted(p_tasks, key=lambda x: (x.get("ordem") or 0, x["created_at"]))
        total = len(p_tasks)
        done = sum(1 for t in p_tasks if t["done"])
        p["progresso"] = f"{done}/{total}" if total else "0/0"
        p["progresso_pct"] = int((done / total) * 100) if total else 0

        # agrupa por "grupo": None vira um grupo "Geral" implícito (sem cabeçalho)
        grupos = {}
        ordem_grupos = []
        for t in p_tasks_sorted:
            chave = t.get("grupo") or None
            if chave not in grupos:
                grupos[chave] = []
                ordem_grupos.append(chave)
            grupos[chave].append(t)

        p["grupos"] = [{"nome": g, "tasks": grupos[g]} for g in ordem_grupos]

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


@app.route("/projects/<project_id>/tasks", methods=["POST"])
def create_task(project_id):
    data = request.json
    raw = data.get("descricao") or ""
    grupo = (data.get("grupo") or "").strip() or None

    partes = re.split(r"[,\n]", raw)
    descricoes = [p.strip() for p in partes if p.strip()]

    if not descricoes:
        return jsonify({"error": "descricao é obrigatória"}), 400

    novas_tasks = [{"project_id": project_id, "descricao": d, "grupo": grupo} for d in descricoes]
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
    Recebe a lista de tasks afetadas após um drag-and-drop, já na ordem final.
    Body esperado:
    {
      "items": [
        {"id": "uuid-1", "grupo": "Importação"},
        {"id": "uuid-2", "grupo": "Importação"},
        {"id": "uuid-3", "grupo": null}
      ]
    }
    Cada item recebe sua posição (índice na lista) como nova "ordem",
    e o "grupo" é atualizado caso a task tenha mudado de seção.
    """
    data = request.json
    items = data.get("items") or []

    if not items:
        return jsonify({"error": "items é obrigatório"}), 400

    for posicao, item in enumerate(items):
        task_id = item.get("id")
        grupo = (item.get("grupo") or "").strip() or None
        if not task_id:
            continue
        supabase.table("tasks").update({
            "ordem": posicao,
            "grupo": grupo
        }).eq("id", task_id).execute()

    return jsonify({"ok": True}), 200


if __name__ == "__main__":
    app.run(debug=True, port=5000)