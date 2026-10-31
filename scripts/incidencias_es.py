"""Pasa al español las incidencias que Upptime abre en inglés (título, cuerpo y comentario de «resuelto»).

Lo lanza .github/workflows/incidencias-es.yml al abrirse una incidencia con la etiqueta «status» o al
comentarse una. Solo toca textos con la forma exacta que genera Upptime, así que los que escribas tú
a mano se quedan como están. Solo biblioteca estándar.

Probar en local:  python scripts/incidencias_es.py --probar
"""
import json
import os
import re
import sys
import urllib.request

UNIDADES = {"day": ("día", "días"), "hour": ("hora", "horas"), "minute": ("minuto", "minutos"), "second": ("segundo", "segundos")}


def titulo(t):
    m = re.fullmatch(r"(🛑\s*)(.+) is down", t)
    if m:
        return f"{m.group(1)}{m.group(2)} no responde"
    m = re.fullmatch(r"(⚠️\s*)(.+) has degraded performance", t)
    if m:
        return f"{m.group(1)}{m.group(2)} va más lento de lo normal"
    return t


def cuerpo(b):
    m = re.fullmatch(r"In (\[`[0-9a-f]+`\]\([^)]+\)), (.+) \((.+?)\) (was \*\*down\*\*|experienced \*\*degraded performance\*\*):\n"
                     r"- HTTP code: (\d+)\n- Response time: (\d+) ms\n?", b, flags=re.S)
    if not m:
        return b
    que = "**no respondía**" if "down" in m.group(4) else "**iba más lento de lo normal**"
    return (f"En {m.group(1)}, {m.group(2)} ({m.group(3)}) {que}:\n"
            f"- Código HTTP: {m.group(5)}\n- Tiempo de respuesta: {m.group(6)} ms\n")


def duracion(d):
    """«1 day, 2 hours, 5 minutes» → «1 día, 2 horas y 5 minutos»."""
    partes = []
    for trozo in [p.strip() for p in d.split(",") if p.strip()]:
        m = re.fullmatch(r"([\d.,]+) (day|hour|minute|second)s?", trozo)
        if not m:
            return d
        n = m.group(1)
        partes.append(f"{n} {UNIDADES[m.group(2)][0 if n == '1' else 1]}")
    if not partes:
        return "menos de un minuto"
    return partes[0] if len(partes) == 1 else ", ".join(partes[:-1]) + " y " + partes[-1]


def comentario(c):
    m = re.fullmatch(r"\*\*Resolved:\*\* (.+) (is back up|performance has improved) in (\[`[0-9a-f]+`\]\([^)]+\)) after (.*)\.", c.strip(), flags=re.S)
    if not m:
        return c
    que = "vuelve a funcionar" if m.group(2) == "is back up" else "vuelve a su velocidad normal"
    return f"**Resuelta:** {m.group(1)} {que} desde {m.group(3)}, tras {duracion(m.group(4))}."


# ---------------------------------------------------------------- GitHub

def _api(metodo, ruta, datos):
    req = urllib.request.Request(f"https://api.github.com{ruta}", method=metodo, data=json.dumps(datos).encode(),
                                 headers={"Authorization": f"Bearer {os.environ['GH_TOKEN']}",
                                          "Accept": "application/vnd.github+json", "User-Agent": "estado-incidencias-es"})
    with urllib.request.urlopen(req, timeout=20) as r:
        return r.status


def main():
    ev = json.load(open(os.environ["GITHUB_EVENT_PATH"], encoding="utf-8"))
    repo = os.environ["GITHUB_REPOSITORY"]
    issue = ev.get("issue") or {}
    if "status" not in [l.get("name") for l in issue.get("labels", [])]:
        return print("No es una incidencia de Upptime: nada que hacer.")
    if ev.get("comment"):
        c = ev["comment"]
        nuevo = comentario(c.get("body") or "")
        if nuevo != c.get("body"):
            _api("PATCH", f"/repos/{repo}/issues/comments/{c['id']}", {"body": nuevo})
            print("Comentario traducido.")
        return
    cambios = {}
    if titulo(issue.get("title") or "") != issue.get("title"):
        cambios["title"] = titulo(issue["title"])
    if cuerpo(issue.get("body") or "") != issue.get("body"):
        cambios["body"] = cuerpo(issue["body"])
    if cambios:
        _api("PATCH", f"/repos/{repo}/issues/{issue['number']}", cambios)
        print("Incidencia traducida:", ", ".join(cambios))


# ---------------------------------------------------------------- pruebas

def probar():
    sha = "[`a1b2c3d`](https://github.com/pab-lit-og/estado/commit/a1b2c3d4)"
    casos = [
        (titulo("🛑 OptiCliniq · web is down"), "🛑 OptiCliniq · web no responde"),
        (titulo("⚠️ OposiVoz has degraded performance"), "⚠️ OposiVoz va más lento de lo normal"),
        (titulo("Mantenimiento programado de OptiCliniq"), "Mantenimiento programado de OptiCliniq"),
        (cuerpo(f"In {sha}, EyeLab (https://eyelab.health/) was **down**:\n- HTTP code: 503\n- Response time: 241 ms\n"),
         f"En {sha}, EyeLab (https://eyelab.health/) **no respondía**:\n- Código HTTP: 503\n- Tiempo de respuesta: 241 ms\n"),
        (cuerpo(f"In {sha}, OposiVoz (https://pab-lit-og.github.io/oposivoz/) experienced **degraded performance**:\n- HTTP code: 200\n- Response time: 12034 ms\n"),
         f"En {sha}, OposiVoz (https://pab-lit-og.github.io/oposivoz/) **iba más lento de lo normal**:\n- Código HTTP: 200\n- Tiempo de respuesta: 12034 ms\n"),
        (cuerpo("Texto escrito a mano"), "Texto escrito a mano"),
        (comentario(f"**Resolved:** OptiCliniq · acceso is back up in {sha} after 23 minutes."),
         f"**Resuelta:** OptiCliniq · acceso vuelve a funcionar desde {sha}, tras 23 minutos."),
        (comentario(f"**Resolved:** EyeLab performance has improved in {sha} after 1 day, 1 hour, 5 minutes."),
         f"**Resuelta:** EyeLab vuelve a su velocidad normal desde {sha}, tras 1 día, 1 hora y 5 minutos."),
        (comentario(f"**Resolved:** EyeLab is back up in {sha} after ."),
         f"**Resuelta:** EyeLab vuelve a funcionar desde {sha}, tras menos de un minuto."),
        (comentario("Estamos en ello: Vercel tiene una incidencia en Europa."), "Estamos en ello: Vercel tiene una incidencia en Europa."),
    ]
    fallos = [(i, a, b) for i, (a, b) in enumerate(casos) if a != b]
    for i, a, b in fallos:
        print(f"FALLA caso {i}:\n  sale:   {a!r}\n  espera: {b!r}")
    print(f"{len(casos) - len(fallos)}/{len(casos)} pruebas bien")
    return not fallos


if __name__ == "__main__":
    if "--probar" in sys.argv:
        sys.exit(0 if probar() else 1)
    main()
