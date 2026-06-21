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
        p["tasks"] = sorted(p_tasks, key=lambda x: x["created_at"])
        total = len(p_tasks)
        done = sum(1 for t in p_tasks if t["done"])
        p["progresso"] = f"{done}/{total}" if total else "0/0"
        p["progresso_pct"] = int((done / total) * 100) if total else 0

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

    partes = re.split(r"[,\n]", raw)
    descricoes = [p.strip() for p in partes if p.strip()]

    if not descricoes:
        return jsonify({"error": "descricao é obrigatória"}), 400

    novas_tasks = [{"project_id": project_id, "descricao": d} for d in descricoes]
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


if __name__ == "__main__":
    app.run(debug=True, port=5000)