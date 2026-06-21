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
    groups = supabase.table("groups").select("*").execute().data

    tasks_by_project = {}
    for t in tasks:
        tasks_by_project.setdefault(t["project_id"], []).append(t)

    groups_by_project = {}
    for g in groups:
        groups_by_project.setdefault(g["project_id"], []).append(g)

    for p in projects:
        p_tasks = tasks_by_project.get(p["id"], [])
        total = len(p_tasks)
        done = sum(1 for t in p_tasks if t["done"])
        p["progresso"] = f"{done}/{total}" if total else "0/0"
        p["progresso_pct"] = int((done / total) * 100) if total else 0

        tasks_by_group = {}
        for t in p_tasks:
            tasks_by_group.setdefault(t.get("group_id"), []).append(t)

        for chave in tasks_by_group:
            tasks_by_group[chave] = sorted(
                tasks_by_group[chave],
                key=lambda x: (x.get("ordem") or 0, x["created_at"])
            )

        p_groups = sorted(groups_by_project.get(p["id"], []), key=lambda g: (g.get("ordem") or 0, g["created_at"]))

        grupos_renderizados = []
        for g in p_groups:
            grupos_renderizados.append({
                "id": g["id"],
                "nome": g["nome"],
                "tasks": tasks_by_group.get(g["id"], [])
            })

        # tasks sem grupo (group_id nulo) ficam soltas no topo, sem cabeçalho
        soltas = tasks_by_group.get(None, [])
        p["soltas"] = soltas
        p["grupos"] = grupos_renderizados

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


@app.route("/projects/<project_id>/groups", methods=["POST"])
def create_group(project_id):
    data = request.json
    nome = (data.get("nome") or "").strip()

    if not nome:
        return jsonify({"error": "nome é obrigatório"}), 400

    result = supabase.table("groups").insert({
        "project_id": project_id,
        "nome": nome
    }).execute()

    return jsonify(result.data[0]), 201


@app.route("/groups/<group_id>", methods=["DELETE"])
def delete_group(group_id):
    # tasks do grupo ficam soltas (group_id vira null) em vez de serem apagadas
    supabase.table("tasks").update({"group_id": None}).eq("group_id", group_id).execute()
    supabase.table("groups").delete().eq("id", group_id).execute()
    return "", 204


@app.route("/projects/<project_id>/tasks", methods=["POST"])
def create_task(project_id):
    data = request.json
    raw = data.get("descricao") or ""
    group_id = data.get("group_id") or None

    partes = re.split(r"[,\n]", raw)
    descricoes = [p.strip() for p in partes if p.strip()]

    if not descricoes:
        return jsonify({"error": "descricao é obrigatória"}), 400

    novas_tasks = [
        {"project_id": project_id, "descricao": d, "group_id": group_id}
        for d in descricoes
    ]
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
    Recebe o estado completo de um projeto após um drag-and-drop: a ordem
    final dos grupos e, dentro de cada um, a ordem final das tasks.

    Body esperado:
    {
      "groups": [
        {"id": "group-uuid-1"},
        {"id": "group-uuid-2"}
      ],
      "tasks": [
        {"id": "task-uuid-1", "group_id": "group-uuid-1"},
        {"id": "task-uuid-2", "group_id": "group-uuid-1"},
        {"id": "task-uuid-3", "group_id": null}
      ]
    }
    """
    data = request.json
    groups = data.get("groups") or []
    tasks = data.get("tasks") or []

    for posicao, g in enumerate(groups):
        group_id = g.get("id")
        if not group_id:
            continue
        supabase.table("groups").update({"ordem": posicao}).eq("id", group_id).execute()

    for posicao, t in enumerate(tasks):
        task_id = t.get("id")
        if not task_id:
            continue
        supabase.table("tasks").update({
            "ordem": posicao,
            "group_id": t.get("group_id")
        }).eq("id", task_id).execute()

    return jsonify({"ok": True}), 200


if __name__ == "__main__":
    app.run(debug=True, port=5000)