#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""TermChat v5.3 — Serveur — by Aboudev Labs CI"""

import socket, threading, json, os, random, hashlib
import datetime, time, base64, signal, sys
import urllib.request, urllib.error

PORT         = int(os.environ.get("PORT", 9999))
GITHUB_TOKEN = os.environ.get("GITHUB_TOKEN", "").strip()
GITHUB_REPO  = os.environ.get("GITHUB_REPO", "daboujohan-hub/termchat").strip()
GITHUB_FILE  = "data/db.json"
ADMIN_CODE   = os.environ.get("ADMIN_CODE", "aboudev2025")

WAVE_NUMBER         = "+2250170404109"
PRIX_PREMIUM        = "1500 FCFA"
DUREE_PREMIUM_JOURS = 60
LIMITE_FICHIER      = 50 * 1024 * 1024   # 50 MB pour les abonnés

DATA_DIR  = os.path.join(os.path.expanduser("~"), ".termchat_data")
DATA_FILE = os.path.join(DATA_DIR, "db.json")
FILES_DIR = os.path.join(DATA_DIR, "files")
github_sha = None

PAYS = {
    "1": ("Cote d'Ivoire", "+225"),
    "2": ("Senegal",       "+221"),
    "3": ("Guinee",        "+224"),
    "4": ("Burkina Faso",  "+226"),
    "5": ("Ghana",         "+233"),
}
STATUTS = ["disponible", "occupe", "ne_pas_deranger", "absent"]

def hacher(s):   return hashlib.sha256(s.encode()).hexdigest()
def horodatage():return datetime.datetime.now().isoformat()
def heure():     return datetime.datetime.now().strftime("%H:%M")

def github_requete(methode, url, body=None):
    headers = {"Authorization": f"token {GITHUB_TOKEN}",
               "Accept": "application/vnd.github.v3+json",
               "Content-Type": "application/json", "User-Agent": "TermChat"}
    data = json.dumps(body).encode() if body else None
    req  = urllib.request.Request(url, data=data, headers=headers, method=methode)
    try:
        with urllib.request.urlopen(req, timeout=15) as r:
            return json.loads(r.read().decode())
    except Exception as e:
        print(f"GitHub erreur ({methode}): {e}"); return None

def telecharger_depuis_github():
    global github_sha
    if not GITHUB_TOKEN: print("Pas de GITHUB_TOKEN - mode local"); return False
    url = f"https://api.github.com/repos/{GITHUB_REPO}/contents/{GITHUB_FILE}"
    rep = github_requete("GET", url)
    if rep and "content" in rep:
        github_sha = rep.get("sha")
        try:
            contenu = base64.b64decode(rep["content"]).decode("utf-8")
            os.makedirs(DATA_DIR, exist_ok=True)
            with open(DATA_FILE, "w", encoding="utf-8") as f: f.write(contenu)
            print("Donnees chargees depuis GitHub"); return True
        except Exception as e: print(f"Erreur decodage: {e}"); return False
    print("Base vide - premier demarrage"); return False

def pousser_sur_github(data):
    global github_sha
    if not GITHUB_TOKEN: return
    try:
        b64 = base64.b64encode(json.dumps(data, ensure_ascii=False, indent=2).encode()).decode()
        url  = f"https://api.github.com/repos/{GITHUB_REPO}/contents/{GITHUB_FILE}"
        body = {"message": "TermChat save", "content": b64}
        if github_sha: body["sha"] = github_sha
        rep = github_requete("PUT", url, body)
        if rep and "content" in rep: github_sha = rep["content"].get("sha")
    except Exception as e: print(f"GitHub save erreur: {e}")

def db_vide():
    return {"users": {}, "historique": {}, "groupes": {}, "canaux": {},
            "demandes_premium": [],
            "stats": {"messages_total": 0, "fichiers_total": 0, "inscriptions_total": 0}}

def charger():
    os.makedirs(DATA_DIR, exist_ok=True); os.makedirs(FILES_DIR, exist_ok=True)
    if not os.path.exists(DATA_FILE): sauver(db_vide())
    with open(DATA_FILE, "r", encoding="utf-8") as f: data = json.load(f)
    for cle, val in db_vide().items(): data.setdefault(cle, val)
    return data

def sauver(data):
    os.makedirs(DATA_DIR, exist_ok=True)
    with open(DATA_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    if GITHUB_TOKEN:
        threading.Thread(target=pousser_sur_github, args=(data,), daemon=True).start()

def initialiser():
    os.makedirs(DATA_DIR, exist_ok=True); os.makedirs(FILES_DIR, exist_ok=True)
    if not telecharger_depuis_github() and not os.path.exists(DATA_FILE): sauver(db_vide())

def trouver_user(data, numero):
    return next((u for u in data["users"].values() if u["numero"] == numero), None)

def trouver_cle_user(data, numero):
    for cle, u in data["users"].items():
        if u["numero"] == numero: return cle
    return None

def gen_numero(prefixe):
    data = charger(); nums = {u["numero"] for u in data["users"].values()}
    while True:
        n = prefixe + str(random.randint(1000000000, 9999999999))
        if n not in nums: return n

def est_premium(user):
    if not user or not user.get("premium"): return False
    expire = user.get("premium_expire")
    return bool(expire and time.time() <= expire)

def sauver_msg(de, vers, texte, type_msg="texte", nom_fich=None,
               chiffre=False, reply_to=None, expire_secondes=None):
    data = charger(); cle = "_".join(sorted([de, vers]))
    data["historique"].setdefault(cle, [])
    msg_id = f"{int(time.time())}_{random.randint(1000,9999)}"
    msg = {"id": msg_id, "de": de, "vers": vers, "texte": texte,
           "type": type_msg, "heure": horodatage(), "lu": False,
           "chiffre": chiffre, "reply_to": reply_to}
    if expire_secondes: msg["expire_a"] = time.time() + int(expire_secondes)
    if nom_fich: msg["fichier"] = nom_fich
    data["historique"][cle].append(msg)
    data["historique"][cle] = data["historique"][cle][-500:]
    data["stats"]["messages_total"] = data["stats"].get("messages_total", 0) + 1
    sauver(data); return msg_id

def get_hist(n1, n2, limite=50):
    data = charger(); cle = "_".join(sorted([n1, n2]))
    hist = data["historique"].get(cle, [])
    now  = time.time()
    return [m for m in hist if not m.get("expire_a") or m["expire_a"] > now][-limite:]

def marquer_lus(dest, exp):
    data = charger(); cle = "_".join(sorted([dest, exp]))
    hist = data["historique"].get(cle, []); changed = False
    for m in hist:
        if m.get("vers") == dest and not m.get("lu"): m["lu"] = True; changed = True
    if changed: data["historique"][cle] = hist; sauver(data)

def compter_non_lus(numero):
    data = charger()
    return sum(1 for msgs in data["historique"].values()
               for m in msgs if m.get("vers") == numero and not m.get("lu"))

def get_conversations(numero):
    data = charger(); convs = []
    noms = {u["numero"]: u["nom"] for u in data["users"].values()}
    now  = time.time()
    for cle, msgs in data["historique"].items():
        nums = cle.split("_")
        if len(nums) != 2 or numero not in nums: continue
        autre = next((n for n in nums if n != numero), None)
        if not autre: continue
        msgs_ok = [m for m in msgs if not m.get("expire_a") or m["expire_a"] > now]
        if not msgs_ok: continue
        dernier = msgs_ok[-1]
        non_lus = sum(1 for m in msgs_ok if m.get("vers") == numero and not m.get("lu"))
        convs.append({"numero": autre, "nom": noms.get(autre, autre),
                      "dernier_msg": dernier.get("texte", "")[:40],
                      "heure": dernier.get("heure", "")[:16].replace("T", " "),
                      "non_lus": non_lus})
    convs.sort(key=lambda x: x["heure"], reverse=True)
    return convs

clients = {}; clients_info = {}; admins_connectes = set()
lock = threading.Lock(); TIMEOUT = 1800

def envoyer_srv(sock, paquet):
    try: sock.sendall((json.dumps(paquet, ensure_ascii=False) + "\n").encode())
    except Exception: pass

def livrer(numero, paquet):
    with lock: s = clients.get(numero)
    if s: envoyer_srv(s, paquet); return True
    return False

def maj_activite(numero):
    with lock:
        if numero in clients_info: clients_info[numero]["derniere_activite"] = time.time()

def notifier_statut(numero, en_ligne, data):
    user = trouver_user(data, numero)
    if not user: return
    with lock: cibles = list(clients.items())
    for num, sock in cibles:
        if num != numero:
            envoyer_srv(sock, {"type": "statut", "numero": numero, "nom": user["nom"], "en_ligne": en_ligne})

def gerer_client(conn, addr):
    num_co = None; buf = ""; est_admin = False

    def moi(data): return trouver_user(data, num_co) if num_co else None

    def need_premium():
        if not num_co: envoyer_srv(conn, {"ok": False, "msg": "Non connecte."}); return False
        data = charger(); user = moi(data)
        if not user: envoyer_srv(conn, {"ok": False, "msg": "Non connecte."}); return False
        if est_premium(user): return True
        if user.get("premium") and not est_premium(user):
            uid = trouver_cle_user(data, num_co)
            if uid: data["users"][uid]["premium"] = False; data["users"][uid]["premium_expire"] = None; sauver(data)
        envoyer_srv(conn, {"ok": False,
            "msg": "Compte non active. Abonne-toi d'abord (menu p -> 1500 FCFA via Wave).",
            "need_premium": True})
        return False

    try:
        while True:
            conn.settimeout(TIMEOUT)
            try: chunk = conn.recv(8192).decode("utf-8", errors="replace")
            except socket.timeout:
                if num_co: envoyer_srv(conn, {"type": "timeout", "msg": "Deconnecte pour inactivite."})
                break
            if not chunk: break
            buf += chunk
            while "\n" in buf:
                ligne, buf = buf.split("\n", 1); ligne = ligne.strip()
                if not ligne: continue
                try: p = json.loads(ligne)
                except Exception: continue
                act = p.get("action", "")
                if num_co: maj_activite(num_co)

                if act == "inscrire":
                    nom = p.get("nom","").strip(); mdp = p.get("mdp","").strip()
                    prefixe = p.get("prefixe","+225").strip(); couleur = p.get("couleur","cyan")
                    if not nom or not mdp: envoyer_srv(conn, {"ok": False, "msg": "Nom et mot de passe requis."})
                    elif len(nom) < 2 or len(nom) > 20: envoyer_srv(conn, {"ok": False, "msg": "Nom: 2 a 20 caracteres."})
                    elif len(mdp) < 4: envoyer_srv(conn, {"ok": False, "msg": "Mot de passe: minimum 4 caracteres."})
                    else:
                        data = charger(); numero = gen_numero(prefixe)
                        pays = next((v[0] for v in PAYS.values() if v[1] == prefixe), "Inconnu")
                        uid  = f"u_{int(time.time())}_{random.randint(1000,9999)}"
                        data["users"][uid] = {
                            "nom": nom, "numero": numero, "mdp": hacher(mdp),
                            "pays": pays, "prefixe": prefixe, "bio": "", "couleur": couleur,
                            "statut": "disponible", "inscription": horodatage(),
                            "derniere_connexion": None, "favoris": [], "bloque": [],
                            "est_admin": False, "premium": False, "premium_expire": None, "pin": None}
                        data["stats"]["inscriptions_total"] = data["stats"].get("inscriptions_total",0) + 1
                        sauver(data); envoyer_srv(conn, {"ok": True, "numero": numero, "nom": nom, "pays": pays})

                elif act == "connecter":
                    nom = p.get("nom","").strip(); mdp = p.get("mdp","").strip(); data = charger()
                    candidats = [(k,u) for k,u in data["users"].items() if u["nom"].lower()==nom.lower()]
                    match = next(((k,u) for k,u in candidats if u["mdp"]==hacher(mdp)), None)
                    if not match:
                        if len(candidats)>1: envoyer_srv(conn, {"ok": False, "msg": "Plusieurs comptes avec ce nom. Connecte-toi avec ton numero.", "utiliser_numero": True})
                        else: envoyer_srv(conn, {"ok": False, "msg": "Nom ou mot de passe incorrect."})
                    else:
                        uid, user = match; num_co = user["numero"]; est_admin = user.get("est_admin", False)
                        data["users"][uid]["derniere_connexion"] = horodatage()
                        is_prem = est_premium(user)
                        if user.get("premium") and not is_prem:
                            data["users"][uid]["premium"] = False; data["users"][uid]["premium_expire"] = None
                        sauver(data)
                        with lock:
                            clients[num_co] = conn
                            clients_info[num_co] = {"nom": user["nom"], "derniere_activite": time.time()}
                            if est_admin: admins_connectes.add(num_co)
                        envoyer_srv(conn, {"ok": True, "nom": user["nom"], "numero": num_co,
                            "pays": user.get("pays",""), "bio": user.get("bio",""),
                            "couleur": user.get("couleur","cyan"), "statut": user.get("statut","disponible"),
                            "est_admin": est_admin, "non_lus": compter_non_lus(num_co),
                            "premium": is_prem, "premium_expire": user.get("premium_expire") if is_prem else None,
                            "a_pin": bool(user.get("pin"))})
                        notifier_statut(num_co, True, data)

                elif act == "connecter_numero":
                    numero = p.get("numero","").strip(); mdp = p.get("mdp","").strip(); data = charger()
                    uid = trouver_cle_user(data, numero); user = data["users"].get(uid) if uid else None
                    if not user or user["mdp"] != hacher(mdp): envoyer_srv(conn, {"ok": False, "msg": "Numero ou mot de passe incorrect."})
                    else:
                        num_co = user["numero"]; est_admin = user.get("est_admin", False)
                        data["users"][uid]["derniere_connexion"] = horodatage()
                        is_prem = est_premium(user)
                        if user.get("premium") and not is_prem:
                            data["users"][uid]["premium"] = False; data["users"][uid]["premium_expire"] = None
                        sauver(data)
                        with lock:
                            clients[num_co] = conn
                            clients_info[num_co] = {"nom": user["nom"], "derniere_activite": time.time()}
                            if est_admin: admins_connectes.add(num_co)
                        envoyer_srv(conn, {"ok": True, "nom": user["nom"], "numero": num_co,
                            "pays": user.get("pays",""), "bio": user.get("bio",""),
                            "couleur": user.get("couleur","cyan"), "statut": user.get("statut","disponible"),
                            "est_admin": est_admin, "non_lus": compter_non_lus(num_co),
                            "premium": is_prem, "premium_expire": user.get("premium_expire") if is_prem else None,
                            "a_pin": bool(user.get("pin"))})
                        notifier_statut(num_co, True, data)

                elif act == "deconnecter": break

                elif act == "typing":
                    if num_co and need_premium():
                        dest = p.get("dest","").strip(); data = charger(); exp = moi(data)
                        if exp: livrer(dest, {"type":"typing","de":exp["nom"],"numero":num_co,"actif":p.get("actif",True)})

                elif act == "chercher":
                    if not num_co: envoyer_srv(conn, {"ok": False, "msg": "Non connecte."})
                    else:
                        numero = p.get("numero","").strip(); data = charger(); trouve = trouver_user(data, numero)
                        if not trouve: envoyer_srv(conn, {"ok": False, "msg": "Utilisateur introuvable."})
                        else:
                            en_ligne = numero in clients; dc = trouve.get("derniere_connexion")
                            if dc: dc = dc[:16].replace("T"," ")
                            envoyer_srv(conn, {"ok": True, "user": {"nom": trouve["nom"], "numero": trouve["numero"],
                                "pays": trouve.get("pays",""), "bio": trouve.get("bio",""),
                                "statut": trouve.get("statut","disponible"), "en_ligne": en_ligne,
                                "derniere_connexion": dc if not en_ligne else None, "premium": est_premium(trouve)}})

                elif act == "mes_conversations":
                    if need_premium(): envoyer_srv(conn, {"ok": True, "conversations": get_conversations(num_co)})

                elif act == "message":
                    if not num_co: envoyer_srv(conn, {"ok": False, "msg": "Non connecte."})
                    elif need_premium():
                        dest = p.get("dest","").strip(); texte = p.get("texte","").strip()
                        chiffre = p.get("chiffre",False); reply_to = p.get("reply_to"); expire_s = p.get("expire_secondes")
                        if not texte or not dest: envoyer_srv(conn, {"ok": False, "msg": "Message ou destinataire vide."})
                        else:
                            data = charger(); exp = moi(data); dest_user = trouver_user(data, dest)
                            if not dest_user: envoyer_srv(conn, {"ok": False, "msg": "Destinataire introuvable."})
                            elif num_co in dest_user.get("bloque",[]): envoyer_srv(conn, {"ok": False, "msg": "Tu es bloque par cet utilisateur."})
                            else:
                                msg_id = sauver_msg(num_co, dest, texte, chiffre=chiffre, reply_to=reply_to, expire_secondes=expire_s)
                                livre  = livrer(dest, {"type":"message","de":exp["nom"] if exp else "?","numero":num_co,
                                    "texte":texte,"heure":heure(),"chiffre":chiffre,"reply_to":reply_to,"msg_id":msg_id})
                                envoyer_srv(conn, {"ok": True, "livre": livre, "msg_id": msg_id})
                                if livre: livrer(num_co, {"type":"livre","dest":dest,"msg_id":msg_id})

                elif act == "reaction":
                    if num_co and need_premium():
                        dest=p.get("dest","").strip(); msg_id=p.get("msg_id",""); emoji=p.get("emoji","👍")
                        data=charger(); exp=moi(data)
                        livrer(dest, {"type":"reaction","de":exp["nom"] if exp else "?","numero":num_co,"msg_id":msg_id,"emoji":emoji,"heure":heure()})
                        envoyer_srv(conn, {"ok": True})

                elif act == "marquer_lu":
                    if num_co:
                        avec = p.get("avec","").strip(); marquer_lus(num_co, avec); livrer(avec, {"type":"lu","par":num_co})

                elif act == "envoyer_fichier":
                    if not num_co: envoyer_srv(conn, {"ok": False, "msg": "Non connecte."})
                    elif need_premium():
                        dest=p.get("dest","").strip(); nom_fich=p.get("nom_fichier","fichier")
                        c64=p.get("contenu",""); taille=p.get("taille",0)
                        data=charger(); exp=moi(data)
                        if taille > LIMITE_FICHIER: envoyer_srv(conn, {"ok": False, "msg": "Fichier trop volumineux (max 50 MB)."})
                        elif not trouver_user(data, dest): envoyer_srv(conn, {"ok": False, "msg": "Destinataire introuvable."})
                        else:
                            safe = "".join(c for c in nom_fich if c.isalnum() or c in "._-") or "fichier"
                            chemin = os.path.join(FILES_DIR, f"{int(time.time())}_{safe}")
                            try:
                                with open(chemin,"wb") as f: f.write(base64.b64decode(c64))
                                sauver_msg(num_co, dest, f"[Fichier] {nom_fich}", "fichier", nom_fich)
                                data2=charger(); data2["stats"]["fichiers_total"]=data2["stats"].get("fichiers_total",0)+1; sauver(data2)
                                livre=livrer(dest, {"type":"fichier","de":exp["nom"] if exp else "?","numero":num_co,
                                    "nom_fichier":nom_fich,"contenu":c64,"taille":taille,"heure":heure()})
                                envoyer_srv(conn, {"ok": True, "livre": livre, "msg": f"'{nom_fich}' envoye."})
                            except Exception as e: envoyer_srv(conn, {"ok": False, "msg": f"Erreur: {e}"})

                elif act == "envoyer_vocal":
                    if not num_co: envoyer_srv(conn, {"ok": False, "msg": "Non connecte."})
                    elif need_premium():
                        dest=p.get("dest","").strip(); c64=p.get("contenu",""); taille=p.get("taille",0); duree=p.get("duree",0)
                        data=charger(); exp=moi(data)
                        if taille > LIMITE_FICHIER: envoyer_srv(conn, {"ok": False, "msg": "Max 50 MB."})
                        elif not trouver_user(data, dest): envoyer_srv(conn, {"ok": False, "msg": "Destinataire introuvable."})
                        else:
                            nom_fich=f"vocal_{int(time.time())}.ogg"; chemin=os.path.join(FILES_DIR, nom_fich)
                            try:
                                with open(chemin,"wb") as f: f.write(base64.b64decode(c64))
                                sauver_msg(num_co, dest, f"[Vocal] {duree}s", "vocal", nom_fich)
                                livre=livrer(dest, {"type":"vocal","de":exp["nom"] if exp else "?","numero":num_co,
                                    "nom_fichier":nom_fich,"contenu":c64,"duree":duree,"taille":taille,"heure":heure()})
                                envoyer_srv(conn, {"ok": True, "livre": livre, "msg": "Vocal envoye!"})
                            except Exception as e: envoyer_srv(conn, {"ok": False, "msg": f"Erreur: {e}"})

                elif act == "historique":
                    if need_premium():
                        avec=p.get("avec","").strip(); hist=get_hist(num_co, avec, p.get("limite",50))
                        data=charger(); noms={u["numero"]:u["nom"] for u in data["users"].values()}
                        for m in hist: m["nom_de"] = noms.get(m["de"], m["de"])
                        marquer_lus(num_co, avec); livrer(avec, {"type":"lu","par":num_co})
                        envoyer_srv(conn, {"ok": True, "historique": hist})

                elif act == "rechercher_msg":
                    if need_premium():
                        mot=p.get("mot","").strip().lower(); avec=p.get("avec","").strip()
                        hist=get_hist(num_co, avec, 500); res=[m for m in hist if mot in m.get("texte","").lower()][-20:]
                        envoyer_srv(conn, {"ok": True, "resultats": res, "total": len(res)})

                elif act == "effacer_historique":
                    if need_premium():
                        avec=p.get("avec","").strip(); data=charger()
                        cle="_".join(sorted([num_co, avec]))
                        if cle in data["historique"]: data["historique"][cle]=[]; sauver(data)
                        envoyer_srv(conn, {"ok": True, "msg": "Historique efface."})

                elif act == "changer_statut":
                    if need_premium():
                        statut=p.get("statut","disponible")
                        if statut not in STATUTS: statut="disponible"
                        data=charger(); uid=trouver_cle_user(data,num_co)
                        if uid:
                            data["users"][uid]["statut"]=statut; sauver(data); nom_u=data["users"][uid]["nom"]
                            with lock: cibles=list(clients.items())
                            for num,sock in cibles:
                                if num!=num_co: envoyer_srv(sock, {"type":"statut_change","numero":num_co,"nom":nom_u,"statut":statut})
                            envoyer_srv(conn, {"ok": True, "msg": f"Statut: {statut}"})

                elif act == "ajouter_favori":
                    if need_premium():
                        cible=p.get("numero","").strip(); data=charger(); uid=trouver_cle_user(data,num_co)
                        if uid:
                            favoris=data["users"][uid].get("favoris",[])
                            if cible not in favoris: favoris.append(cible)
                            data["users"][uid]["favoris"]=favoris; sauver(data)
                            envoyer_srv(conn, {"ok": True, "msg": "Ajoute aux favoris!"})

                elif act == "mes_favoris":
                    if need_premium():
                        data=charger(); user=moi(data); favoris=user.get("favoris",[]) if user else []
                        with lock: ens=set(clients.keys())
                        result=[{"nom":trouver_user(data,n)["nom"],"numero":n,
                            "statut":trouver_user(data,n).get("statut","disponible"),"en_ligne":n in ens}
                            for n in favoris if trouver_user(data,n)]
                        envoyer_srv(conn, {"ok": True, "favoris": result})

                elif act == "bloquer":
                    if num_co:
                        cible=p.get("numero","").strip(); action=p.get("bloquer",True)
                        data=charger(); uid=trouver_cle_user(data,num_co)
                        if uid:
                            bloque=data["users"][uid].get("bloque",[])
                            if action and cible not in bloque: bloque.append(cible)
                            elif not action and cible in bloque: bloque.remove(cible)
                            data["users"][uid]["bloque"]=bloque; sauver(data)
                            envoyer_srv(conn, {"ok": True, "msg": "Bloque." if action else "Debloque."})

                elif act == "changer_couleur":
                    if num_co:
                        couleur=p.get("couleur","cyan"); data=charger(); uid=trouver_cle_user(data,num_co)
                        if uid: data["users"][uid]["couleur"]=couleur; sauver(data); envoyer_srv(conn, {"ok":True,"msg":"Couleur changee!","couleur":couleur})

                elif act == "modifier_bio":
                    if num_co:
                        bio=p.get("bio","").strip()[:150]; data=charger(); uid=trouver_cle_user(data,num_co)
                        if uid: data["users"][uid]["bio"]=bio; sauver(data); envoyer_srv(conn, {"ok":True,"msg":"Bio mise a jour!"})

                elif act == "changer_mdp":
                    if not num_co: envoyer_srv(conn, {"ok":False,"msg":"Non connecte."})
                    else:
                        ancien=p.get("ancien","").strip(); nouveau=p.get("nouveau","").strip()
                        data=charger(); uid=trouver_cle_user(data,num_co)
                        if len(nouveau)<4: envoyer_srv(conn, {"ok":False,"msg":"Min 4 caracteres."})
                        elif not uid or data["users"][uid]["mdp"]!=hacher(ancien): envoyer_srv(conn, {"ok":False,"msg":"Ancien mot de passe incorrect."})
                        else: data["users"][uid]["mdp"]=hacher(nouveau); sauver(data); envoyer_srv(conn, {"ok":True,"msg":"Mot de passe change!"})

                elif act == "supprimer_compte":
                    if not num_co: envoyer_srv(conn, {"ok":False,"msg":"Non connecte."})
                    else:
                        mdp=p.get("mdp","").strip(); data=charger(); uid=trouver_cle_user(data,num_co)
                        if not uid or data["users"][uid]["mdp"]!=hacher(mdp): envoyer_srv(conn, {"ok":False,"msg":"Mot de passe incorrect."})
                        else: del data["users"][uid]; sauver(data); envoyer_srv(conn, {"ok":True,"msg":"Compte supprime."}); num_co=None

                elif act == "definir_pin":
                    if num_co:
                        pin=p.get("pin","").strip()
                        if len(pin)!=4 or not pin.isdigit(): envoyer_srv(conn, {"ok":False,"msg":"Le PIN doit etre 4 chiffres."})
                        else:
                            data=charger(); uid=trouver_cle_user(data,num_co)
                            if uid: data["users"][uid]["pin"]=hacher(pin); sauver(data); envoyer_srv(conn, {"ok":True,"msg":"Code PIN active!"})

                elif act == "supprimer_pin":
                    if num_co:
                        data=charger(); uid=trouver_cle_user(data,num_co)
                        if uid: data["users"][uid]["pin"]=None; sauver(data); envoyer_srv(conn, {"ok":True,"msg":"Code PIN desactive."})

                elif act == "verifier_pin":
                    if num_co:
                        pin=p.get("pin","").strip(); data=charger(); user=moi(data)
                        if not user or not user.get("pin"): envoyer_srv(conn, {"ok":True,"msg":"Pas de PIN defini."})
                        elif user["pin"]==hacher(pin): envoyer_srv(conn, {"ok":True,"msg":"PIN correct."})
                        else: envoyer_srv(conn, {"ok":False,"msg":"PIN incorrect."})

                elif act == "creer_groupe":
                    if need_premium():
                        nom_g=p.get("nom","").strip()
                        if nom_g:
                            data=charger(); id_g=f"grp_{int(time.time())}_{random.randint(1000,9999)}"
                            data["groupes"][id_g]={"nom":nom_g,"createur":num_co,"membres":[num_co],"creation":horodatage(),"historique":[],"epingle":None}
                            sauver(data); envoyer_srv(conn, {"ok":True,"id_groupe":id_g,"nom":nom_g})

                elif act == "ajouter_groupe":
                    if need_premium():
                        id_g=p.get("id_groupe","").strip(); cible=p.get("numero","").strip(); data=charger()
                        groupe=data["groupes"].get(id_g)
                        if not groupe: envoyer_srv(conn, {"ok":False,"msg":"Groupe introuvable."})
                        elif groupe["createur"]!=num_co: envoyer_srv(conn, {"ok":False,"msg":"Seul le createur peut ajouter."})
                        elif not trouver_user(data,cible): envoyer_srv(conn, {"ok":False,"msg":"Utilisateur introuvable."})
                        elif cible in groupe["membres"]: envoyer_srv(conn, {"ok":False,"msg":"Deja membre."})
                        else:
                            groupe["membres"].append(cible); sauver(data)
                            livrer(cible, {"type":"invitation_groupe","groupe":groupe["nom"],"id_groupe":id_g,"heure":heure()})
                            envoyer_srv(conn, {"ok":True,"msg":"Membre ajoute!"})

                elif act == "epingler_groupe":
                    if need_premium():
                        id_g=p.get("id_groupe","").strip(); texte=p.get("texte","").strip(); data=charger()
                        groupe=data["groupes"].get(id_g)
                        if not groupe: envoyer_srv(conn, {"ok":False,"msg":"Groupe introuvable."})
                        elif groupe["createur"]!=num_co: envoyer_srv(conn, {"ok":False,"msg":"Acces refuse."})
                        else:
                            groupe["epingle"]=texte; sauver(data)
                            for m in groupe["membres"]: livrer(m, {"type":"epingle","groupe":groupe["nom"],"texte":texte,"heure":heure()})
                            envoyer_srv(conn, {"ok":True,"msg":"Message epingle!"})

                elif act == "msg_groupe":
                    if need_premium():
                        id_g=p.get("id_groupe","").strip(); texte=p.get("texte","").strip(); reply=p.get("reply_to")
                        data=charger(); groupe=data["groupes"].get(id_g)
                        if groupe and num_co in groupe.get("membres",[]) and texte:
                            exp=moi(data)
                            for m in groupe["membres"]:
                                if m!=num_co: livrer(m, {"type":"msg_groupe","groupe":groupe["nom"],"id_groupe":id_g,
                                    "de":exp["nom"] if exp else "?","numero":num_co,"texte":texte,"heure":heure(),"reply_to":reply})
                            groupe.setdefault("historique",[]).append({"de":num_co,"nom":exp["nom"] if exp else "?","texte":texte,"heure":horodatage(),"reply_to":reply})
                            groupe["historique"]=groupe["historique"][-500:]; sauver(data); envoyer_srv(conn, {"ok":True})
                        else: envoyer_srv(conn, {"ok":False,"msg":"Groupe introuvable ou non membre."})

                elif act == "mes_groupes":
                    if need_premium():
                        data=charger()
                        groupes=[{"id":gid,"nom":g["nom"],"membres":len(g["membres"]),"createur":g["createur"]==num_co,"epingle":g.get("epingle")}
                            for gid,g in data["groupes"].items() if num_co in g.get("membres",[])]
                        envoyer_srv(conn, {"ok":True,"groupes":groupes})

                elif act == "creer_canal":
                    if need_premium():
                        nom_c=p.get("nom","").strip(); desc=p.get("description","").strip()[:150]
                        if nom_c and len(nom_c)>=2:
                            data=charger(); id_c=f"canal_{int(time.time())}_{random.randint(1000,9999)}"; exp=moi(data)
                            data["canaux"][id_c]={"nom":nom_c,"description":desc,"createur":num_co,
                                "createur_nom":exp["nom"] if exp else "?","membres":[num_co],"creation":horodatage(),"historique":[]}
                            sauver(data); envoyer_srv(conn, {"ok":True,"id_canal":id_c,"nom":nom_c})

                elif act == "lister_canaux":
                    data=charger()
                    canaux=[{"id":cid,"nom":c["nom"],"description":c.get("description",""),"membres":len(c["membres"]),"createur":c.get("createur_nom","?")}
                        for cid,c in data["canaux"].items()]
                    envoyer_srv(conn, {"ok":True,"canaux":canaux})

                elif act == "rejoindre_canal":
                    if need_premium():
                        id_c=p.get("id_canal","").strip(); data=charger(); canal=data["canaux"].get(id_c)
                        if not canal: envoyer_srv(conn, {"ok":False,"msg":"Canal introuvable."})
                        else:
                            if num_co not in canal["membres"]: canal["membres"].append(num_co); sauver(data)
                            envoyer_srv(conn, {"ok":True,"nom":canal["nom"]})

                elif act == "msg_canal":
                    if need_premium():
                        id_c=p.get("id_canal","").strip(); texte=p.get("texte","").strip(); data=charger(); canal=data["canaux"].get(id_c)
                        if canal and num_co in canal.get("membres",[]) and texte:
                            exp=moi(data)
                            for m in canal["membres"]:
                                if m!=num_co: livrer(m, {"type":"msg_canal","canal":canal["nom"],"id_canal":id_c,
                                    "de":exp["nom"] if exp else "?","numero":num_co,"texte":texte,"heure":heure()})
                            canal.setdefault("historique",[]).append({"de":num_co,"nom":exp["nom"] if exp else "?","texte":texte,"heure":horodatage()})
                            canal["historique"]=canal["historique"][-200:]; sauver(data); envoyer_srv(conn, {"ok":True})
                        else: envoyer_srv(conn, {"ok":False,"msg":"Canal introuvable ou non membre."})

                elif act == "hist_canal":
                    if need_premium():
                        id_c=p.get("id_canal","").strip(); data=charger(); canal=data["canaux"].get(id_c)
                        if not canal: envoyer_srv(conn, {"ok":False,"msg":"Canal introuvable."})
                        else: envoyer_srv(conn, {"ok":True,"historique":canal.get("historique",[])[-30:],"nom":canal["nom"]})

                elif act == "en_ligne":
                    with lock: liste=list(clients.keys())
                    data=charger(); noms={u["numero"]:u["nom"] for u in data["users"].values()}
                    statuts={u["numero"]:u.get("statut","disponible") for u in data["users"].values()}
                    envoyer_srv(conn, {"ok":True,"users":[{"numero":n,"nom":noms.get(n,"?"),"statut":statuts.get(n,"disponible")} for n in liste if n!=num_co]})

                elif act == "info_premium":
                    data=charger(); user=moi(data); is_p=est_premium(user) if user else False
                    envoyer_srv(conn, {"ok":True,"premium":is_p,"premium_expire":user.get("premium_expire") if (user and is_p) else None,
                        "wave":WAVE_NUMBER,"prix":PRIX_PREMIUM,"duree_jours":DUREE_PREMIUM_JOURS})

                elif act == "demander_premium":
                    if not num_co: envoyer_srv(conn, {"ok":False,"msg":"Non connecte."})
                    else:
                        code=p.get("code","").strip()
                        if not code: envoyer_srv(conn, {"ok":False,"msg":"Code de transaction requis."})
                        else:
                            data=charger(); exp=moi(data)
                            demande={"numero":num_co,"nom":exp["nom"] if exp else "?","code":code,"heure":horodatage(),"statut":"attente"}
                            data["demandes_premium"].append(demande); sauver(data)
                            with lock: admins=list(admins_connectes)
                            for adm in admins: livrer(adm, {"type":"nouvelle_demande_premium","nom":demande["nom"],"numero":num_co,"code":code,"heure":demande["heure"]})
                            envoyer_srv(conn, {"ok":True,"msg":"Demande envoyee! En attente de confirmation."})

                elif act == "demandes_premium":
                    if not est_admin: envoyer_srv(conn, {"ok":False,"msg":"Acces refuse."})
                    else:
                        data=charger(); attente=[d for d in data["demandes_premium"] if d.get("statut")=="attente"]
                        envoyer_srv(conn, {"ok":True,"demandes":attente})

                elif act == "confirmer_premium":
                    if not est_admin: envoyer_srv(conn, {"ok":False,"msg":"Acces refuse."})
                    else:
                        cible=p.get("numero","").strip(); data=charger()
                        for d in data["demandes_premium"]:
                            if d["numero"]==cible and d["statut"]=="attente": d["statut"]="confirme"
                        uid=trouver_cle_user(data,cible)
                        if not uid: envoyer_srv(conn, {"ok":False,"msg":"Utilisateur introuvable."})
                        else:
                            expire_a=time.time()+DUREE_PREMIUM_JOURS*86400
                            data["users"][uid]["premium"]=True; data["users"][uid]["premium_expire"]=expire_a; sauver(data)
                            expire_str=datetime.datetime.fromtimestamp(expire_a).strftime("%d/%m/%Y")
                            livrer(cible, {"type":"premium_active","expire":expire_a,"expire_str":expire_str,"jours":DUREE_PREMIUM_JOURS})
                            envoyer_srv(conn, {"ok":True,"msg":f"Premium active pour {cible} jusqu'au {expire_str}!"})

                elif act == "rejeter_premium":
                    if not est_admin: envoyer_srv(conn, {"ok":False,"msg":"Acces refuse."})
                    else:
                        cible=p.get("numero","").strip(); data=charger()
                        for d in data["demandes_premium"]:
                            if d["numero"]==cible and d["statut"]=="attente": d["statut"]="rejete"
                        sauver(data); livrer(cible, {"type":"premium_rejete"})
                        envoyer_srv(conn, {"ok":True,"msg":"Demande rejetee."})

                elif act == "admin_login":
                    if p.get("code","") == ADMIN_CODE:
                        est_admin=True
                        if num_co:
                            with lock: admins_connectes.add(num_co)
                        envoyer_srv(conn, {"ok":True,"msg":"Acces admin accorde."})
                    else: envoyer_srv(conn, {"ok":False,"msg":"Code incorrect."})

                elif act == "admin_stats":
                    if not est_admin: envoyer_srv(conn, {"ok":False,"msg":"Acces refuse."})
                    else:
                        data=charger()
                        with lock: en_ligne=len(clients)
                        stats=data.get("stats",{})
                        envoyer_srv(conn, {"ok":True,"stats":{"utilisateurs":len(data["users"]),"en_ligne":en_ligne,
                            "messages_total":stats.get("messages_total",0),"fichiers_total":stats.get("fichiers_total",0),
                            "inscriptions_total":stats.get("inscriptions_total",0),
                            "groupes":len(data["groupes"]),"canaux":len(data["canaux"]),"conversations":len(data["historique"])}})

                elif act == "admin_broadcast":
                    if not est_admin: envoyer_srv(conn, {"ok":False,"msg":"Acces refuse."})
                    else:
                        msg=p.get("msg","").strip()
                        with lock: tous=list(clients.values())
                        for s in tous: envoyer_srv(s, {"type":"annonce","msg":msg,"heure":heure()})
                        envoyer_srv(conn, {"ok":True,"msg":f"Envoye a {len(tous)} utilisateurs."})

                elif act == "admin_users":
                    if not est_admin: envoyer_srv(conn, {"ok":False,"msg":"Acces refuse."})
                    else:
                        data=charger()
                        with lock: ens=set(clients.keys())
                        users=[{"nom":u["nom"],"numero":u["numero"],"pays":u.get("pays",""),
                            "inscription":(u.get("inscription") or "")[:10],
                            "derniere_connexion":(u.get("derniere_connexion") or "—")[:16],
                            "statut":u.get("statut","disponible"),"premium":est_premium(u),"en_ligne":u["numero"] in ens}
                            for u in data["users"].values()]
                        envoyer_srv(conn, {"ok":True,"users":users})

                elif act == "admin_kick":
                    if not est_admin: envoyer_srv(conn, {"ok":False,"msg":"Acces refuse."})
                    else:
                        cible=p.get("numero","").strip()
                        with lock: s=clients.get(cible)
                        if s:
                            envoyer_srv(s, {"type":"kick","msg":"Deconnecte par l'administrateur."})
                            try: s.close()
                            except Exception: pass
                            envoyer_srv(conn, {"ok":True,"msg":"Utilisateur deconnecte."})
                        else: envoyer_srv(conn, {"ok":False,"msg":"Utilisateur hors ligne."})

                else: envoyer_srv(conn, {"ok":False,"msg":f"Action inconnue: {act}"})

    except Exception: pass
    finally:
        if num_co:
            with lock: clients.pop(num_co,None); clients_info.pop(num_co,None); admins_connectes.discard(num_co)
            try: data=charger(); notifier_statut(num_co,False,data)
            except Exception: pass
        try: conn.close()
        except Exception: pass

def main():
    print("TERMCHAT v5.3 — SERVEUR — by Aboudev Labs CI")
    initialiser()
    srv=socket.socket(socket.AF_INET,socket.SOCK_STREAM)
    srv.setsockopt(socket.SOL_SOCKET,socket.SO_REUSEADDR,1)
    srv.bind(("0.0.0.0",PORT)); srv.listen(200)
    print(f"TCP port {PORT} | GitHub: {GITHUB_REPO}")
    def quitter(sig,frame): srv.close(); sys.exit(0)
    signal.signal(signal.SIGINT,quitter); signal.signal(signal.SIGTERM,quitter)
    while True:
        try:
            conn,addr=srv.accept()
            threading.Thread(target=gerer_client,args=(conn,addr),daemon=True).start()
        except Exception: break

if __name__=="__main__": main()
