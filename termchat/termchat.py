#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""TermChat v5.3 — Client — by Aboudev Labs CI"""

import socket, threading, json, os, base64
import datetime, time, sys, signal, hashlib

R="\033[91m"; B="\033[1m"; Z="\033[0m"; G="\033[90m"; V="\033[92m"; J="\033[93m"; M="\033[95m"
COULEURS={"cyan":"\033[96m","vert":"\033[92m","jaune":"\033[93m","magenta":"\033[95m","bleu":"\033[94m","rouge":"\033[91m","blanc":"\033[97m"}
STATUTS_ICONS={"disponible":f"{V}🟢 Disponible{Z}","occupe":f"{J}🟡 Occupe{Z}","ne_pas_deranger":f"{R}🔴 Ne pas deranger{Z}","absent":f"{G}⚫ Absent{Z}"}

DOWNLOADS=os.path.join(os.path.expanduser("~"),"termchat_downloads")
os.makedirs(DOWNLOADS, exist_ok=True)

PAYS={"1":("🇨🇮 Cote d'Ivoire","+225"),"2":("🇸🇳 Senegal","+221"),"3":("🇬🇳 Guinee","+224"),"4":("🇧🇫 Burkina Faso","+226"),"5":("🇬🇭 Ghana","+233")}

session={"connecte":False,"nom":None,"numero":None,"pays":None,"bio":"","couleur":"cyan","statut":"disponible","est_admin":False,"non_lus":0,"premium":False,"a_pin":False}
sock_cli=None; en_cours=True; reponses=[]; rep_lock=threading.Lock()

def generer_cle(n1,n2): return hashlib.sha256("".join(sorted([n1,n2])).encode()).hexdigest()
def chiffrer(t,cle):
    try:
        o=t.encode(); k=(cle*((len(o)//len(cle))+1)).encode()
        return base64.b64encode(bytes(a^b for a,b in zip(o,k))).decode()
    except: return t
def dechiffrer(t64,cle):
    try:
        o=base64.b64decode(t64.encode()); k=(cle*((len(o)//len(cle))+1)).encode()
        return bytes(a^b for a,b in zip(o,k)).decode("utf-8")
    except: return t64

def clear(): os.system("clear" if os.name!="nt" else "cls")
def beep(): print("\a",end="",flush=True)
def get_C(): return COULEURS.get(session.get("couleur","cyan"),"\033[96m")
def fmt(o):
    if o<1024: return f"{o} o"
    elif o<1024**2: return f"{o//1024} Ko"
    else: return f"{o//1024//1024} Mo"
def titre(t):
    C2=get_C()
    print(f"\n{C2}{B}{'─'*46}{Z}")
    print(f"{C2}{B}  {t}{Z}")
    print(f"{C2}{B}{'─'*46}{Z}\n")
def succes(m): print(f"{V}{B}✅  {m}{Z}")
def erreur(m): print(f"{R}❌  {m}{Z}")
def info(m):   print(f"{J}ℹ️   {m}{Z}")
def entree():  input(f"\n{G}[Entree pour continuer]{Z}")

def banniere():
    clear(); C2=get_C()
    print(f"""
{C2}{B}╔══════════════════════════════════════════════╗
║                                              ║
║   💬   T E R M C H A T   v5.3              ║
║   Messagerie pour Developpeurs               ║
║   by Aboudev Labs 🇨🇮                        ║
║                                              ║
╚══════════════════════════════════════════════╝{Z}
""")

def envoyer_cli(p):
    try: sock_cli.sendall((json.dumps(p,ensure_ascii=False)+"\n").encode())
    except Exception as e: erreur(f"Reseau: {e}")

def attendre(timeout=6):
    debut=time.time()
    while time.time()-debut<timeout:
        with rep_lock:
            if reponses: return reponses.pop(0)
        time.sleep(0.05)
    return None

def recevoir():
    global en_cours; buf=""
    while en_cours:
        try:
            chunk=sock_cli.recv(8192).decode("utf-8",errors="replace")
            if not chunk: en_cours=False; break
            buf+=chunk
            while "\n" in buf:
                ligne,buf=buf.split("\n",1); ligne=ligne.strip()
                if not ligne: continue
                try: p=json.loads(ligne)
                except Exception: continue
                if "type" in p: afficher_entrant(p)
                else:
                    with rep_lock: reponses.append(p)
        except Exception:
            if en_cours: print(f"\n{R}Connexion perdue.{Z}")
            en_cours=False; break

def afficher_entrant(p):
    C2=get_C(); t=p.get("type",""); h=p.get("heure","")
    if t=="message":
        num_exp=p.get("numero",""); texte=p.get("texte","")
        if p.get("chiffre") and session.get("numero"):
            texte=dechiffrer(texte,generer_cle(session["numero"],num_exp))
        beep(); reply=p.get("reply_to")
        print(f"\n{V}{B}[{h}] 💬 {p.get('de','?')} ({num_exp}){Z}")
        if reply: print(f"{G}     ↩️  {reply[:40]}{Z}")
        print(f"     {texte}")
        if p.get("chiffre"): print(f"{G}     🔐 Chiffre{Z}")
        print(f"{G}> {Z}",end="",flush=True)
    elif t=="typing":
        if p.get("actif"): print(f"\r{G}  ✍️  {p.get('de','?')} ecrit...{Z}    ",end="",flush=True)
        else: print(f"\r{' '*50}\r",end="",flush=True)
    elif t=="livre": print(f"\r{G}  ✓ Livre{Z}  ",end="",flush=True)
    elif t=="lu": print(f"\r{G}  ✓✓ Lu{Z}  ",end="",flush=True)
    elif t=="reaction":
        print(f"\n{J}  {p.get('emoji','👍')} {p.get('de','?')} a reagi{Z}")
        print(f"{G}> {Z}",end="",flush=True)
    elif t=="fichier":
        nom_f=p.get("nom_fichier","fichier"); taille=p.get("taille",0); beep()
        print(f"\n{M}{B}[{h}] 📎 {p.get('de','?')} → {nom_f} ({fmt(taille)}){Z}")
        chemin=os.path.join(DOWNLOADS,nom_f); base_,ext=os.path.splitext(nom_f); c=1
        while os.path.exists(chemin): chemin=os.path.join(DOWNLOADS,f"{base_}_{c}{ext}"); c+=1
        try:
            with open(chemin,"wb") as f: f.write(base64.b64decode(p.get("contenu","")))
            print(f"{V}     ✅ Sauvegarde: {chemin}{Z}")
        except Exception as e: print(f"{R}     ❌ {e}{Z}")
        print(f"{G}> {Z}",end="",flush=True)
    elif t=="vocal":
        nom_f=p.get("nom_fichier","vocal.ogg"); duree=p.get("duree",0); beep()
        print(f"\n{M}{B}[{h}] 🎙️  {p.get('de','?')} → Message vocal ({duree}s){Z}")
        chemin=os.path.join(DOWNLOADS,nom_f)
        try:
            with open(chemin,"wb") as f: f.write(base64.b64decode(p.get("contenu","")))
            print(f"{V}     ✅ {chemin}{Z}")
            print(f"{G}     ▶️  termux-media-player play {chemin}{Z}")
        except Exception as e: print(f"{R}     ❌ {e}{Z}")
        print(f"{G}> {Z}",end="",flush=True)
    elif t=="msg_groupe":
        beep(); reply=p.get("reply_to")
        print(f"\n{C2}{B}[{h}] 👥 [{p.get('groupe','?')}] {p.get('de','?')}{Z}")
        if reply: print(f"{G}     ↩️  {reply[:40]}{Z}")
        print(f"     {p.get('texte','')}")
        print(f"{G}> {Z}",end="",flush=True)
    elif t=="msg_canal":
        beep()
        print(f"\n{J}{B}[{h}] 📡 [{p.get('canal','?')}] {p.get('de','?')}{Z}")
        print(f"     {p.get('texte','')}")
        print(f"{G}> {Z}",end="",flush=True)
    elif t=="invitation_groupe":
        beep(); print(f"\n{J}{B}📩 Ajoute au groupe '{p.get('groupe','?')}' !{Z}")
        print(f"{G}> {Z}",end="",flush=True)
    elif t=="epingle":
        print(f"\n{J}{B}📌 [{p.get('groupe','?')}] Epingle: {p.get('texte','')}{Z}")
        print(f"{G}> {Z}",end="",flush=True)
    elif t=="statut":
        icone=f"{V}🟢{Z}" if p.get("en_ligne") else f"{G}⚫{Z}"
        print(f"\n{G}  {icone} {p.get('nom','?')} {'en ligne' if p.get('en_ligne') else 'hors ligne'}{Z}")
        print(f"{G}> {Z}",end="",flush=True)
    elif t=="statut_change":
        st=STATUTS_ICONS.get(p.get("statut",""),"")
        print(f"\n{G}  {p.get('nom','?')} → {st}{Z}")
        print(f"{G}> {Z}",end="",flush=True)
    elif t=="premium_active":
        beep(); beep()
        print(f"\n{J}{B}⭐ FELICITATIONS! Compte active jusqu'au {p.get('expire_str','')}!{Z}")
        session["premium"]=True
        print(f"{G}> {Z}",end="",flush=True)
    elif t=="premium_rejete":
        print(f"\n{R}❌ Demande Premium rejetee. Verifie le code et reessaie.{Z}")
        print(f"{G}> {Z}",end="",flush=True)
    elif t=="nouvelle_demande_premium":
        beep(); beep(); beep()
        print(f"\n{J}{B}💰 NOUVELLE DEMANDE PREMIUM!{Z}")
        print(f"   👤 {p.get('nom','?')}  📱 {p.get('numero','')}")
        print(f"   🔑 Code: {p.get('code','')}")
        print(f"   🕐 Heure: {p.get('heure','')[:16].replace('T',' ')}")
        print(f"{J}   → Admin → option p pour confirmer{Z}")
        print(f"{G}> {Z}",end="",flush=True)
    elif t=="annonce":
        beep(); beep()
        print(f"\n{J}{B}📢 ANNONCE [{h}]: {p.get('msg','')}{Z}")
        print(f"{G}> {Z}",end="",flush=True)
    elif t=="timeout":
        print(f"\n{J}⏱️  {p.get('msg','Deconnecte.')}{Z}")
        en_cours=False
    elif t=="kick":
        msg_kick=p.get("msg","Deconnecte par l'administrateur.")
        print(f"\n{R}{B}⛔ {msg_kick}{Z}")
        en_cours=False

def menu_accueil():
    banniere(); C2=get_C()
    print(f"  {C2}1{Z} — 🆕  Creer un compte")
    print(f"  {C2}2{Z} — 🔑  Se connecter")
    print(f"  {C2}3{Z} — 📱  Se connecter par numero")
    print(f"  {C2}q{Z} — 🚪  Quitter\n")
    return input(f"{J}Choix: {Z}").strip().lower()

def menu_principal():
    banniere(); C2=get_C()
    nom=session.get("nom",""); num=session.get("numero","")
    nl=session.get("non_lus",0); st=STATUTS_ICONS.get(session.get("statut","disponible"),"")
    badge=f" {R}[{nl} non lus]{Z}" if nl>0 else ""
    admin=f" {J}[ADMIN]{Z}" if session.get("est_admin") else ""
    prem=f" {J}⭐ ABONNE{Z}" if session.get("premium") else f" {R}⛔ NON ABONNE{Z}"
    print(f"{C2}{B}┌─────────────────────────────────────────┐")
    print(f"│  👤  {nom:<15} {num:<20}│")
    print(f"└─────────────────────────────────────────┘{Z} {st}{badge}{admin}{prem}\n")
    if not session.get("premium"):
        print(f"{R}{B}  ⛔ Compte non active — Abonne-toi pour utiliser TermChat{Z}")
        print(f"  {C2}p{Z} — 💰  S'abonner (1500 FCFA)")
        print(f"  {C2}s{Z} — 🛡️   Securite (changer mdp, supprimer compte)")
        print(f"  {C2}q{Z} — 🚪  Deconnecter\n")
    else:
        print(f"  {C2}1{Z} — 💬  Messages")
        print(f"  {C2}2{Z} — 👥  Groupes")
        print(f"  {C2}3{Z} — ⭐  Favoris")
        print(f"  {C2}4{Z} — 📎  Envoyer un fichier")
        print(f"  {C2}5{Z} — 🔍  Chercher un utilisateur")
        print(f"  {C2}6{Z} — 🌐  En ligne")
        print(f"  {C2}7{Z} — 👤  Mon profil")
        print(f"  {C2}8{Z} — 😊  Statut")
        print(f"  {C2}9{Z} — 🎨  Couleur")
        print(f"  {C2}c{Z} — 📡  Canaux publics")
        print(f"  {C2}p{Z} — 💰  Mon abonnement")
        print(f"  {C2}s{Z} — 🛡️   Securite")
        if session.get("est_admin"): print(f"  {C2}0{Z} — ⚙️   Panel Admin")
        print(f"  {C2}q{Z} — 🚪  Deconnecter\n")
    return input(f"{J}Choix: {Z}").strip().lower()

def inscrire():
    titre("🆕 CREER UN COMPTE")
    print(f"{J}ℹ️  Apres la creation, abonne-toi pour utiliser l'app.{Z}\n")
    nom=input("Ton nom (2-20 car.): ").strip()
    if not nom: erreur("Nom requis."); entree(); return
    mdp=input("Mot de passe (min 4): ").strip()
    if not mdp: erreur("Mot de passe requis."); entree(); return
    mdp2=input("Confirmer le mot de passe: ").strip()
    if mdp!=mdp2: erreur("Les mots de passe ne correspondent pas."); entree(); return
    print(f"\n{B}Choisis ton pays:{Z}\n")
    for k,(flag_nom,prefixe) in PAYS.items(): print(f"  {k} — {flag_nom}  ({prefixe})")
    choix_pays=input("\nNumero du pays: ").strip()
    if choix_pays not in PAYS: choix_pays="1"
    _,prefixe=PAYS[choix_pays]
    envoyer_cli({"action":"inscrire","nom":nom,"mdp":mdp,"prefixe":prefixe})
    rep=attendre()
    if rep and rep.get("ok"):
        numero=rep["numero"]; pays=rep.get("pays","")
        print(f"""
{V}{B}╔══════════════════════════════════════════╗
║   ✅  Compte cree avec succes!           ║
╠══════════════════════════════════════════╣
║   👤  {nom:<36}║
║   📱  {numero:<36}║
║   🌍  {pays:<36}║
╚══════════════════════════════════════════╝{Z}
{J}⚠️  Note bien ton numero - c'est ton identifiant!
   Connecte-toi et abonne-toi pour commencer (1500 FCFA).{Z}
""")
    else: erreur(rep.get("msg","Erreur") if rep else "Pas de reponse.")
    entree()

def connecter():
    titre("🔑 SE CONNECTER")
    nom=input("Ton nom: ").strip(); mdp=input("Mot de passe: ").strip()
    envoyer_cli({"action":"connecter","nom":nom,"mdp":mdp}); rep=attendre()
    if rep and rep.get("ok"): _finaliser_connexion(rep); return
    if rep and rep.get("utiliser_numero"): info("Plusieurs comptes avec ce nom. Connecte-toi par numero."); entree(); connecter_par_numero(); return
    erreur(rep.get("msg","Erreur") if rep else "Pas de reponse."); entree()

def connecter_par_numero():
    titre("📱 CONNEXION PAR NUMERO")
    numero=input("Ton numero: ").strip(); mdp=input("Mot de passe: ").strip()
    envoyer_cli({"action":"connecter_numero","numero":numero,"mdp":mdp}); rep=attendre()
    if rep and rep.get("ok"): _finaliser_connexion(rep); return
    erreur(rep.get("msg","Erreur") if rep else "Pas de reponse."); entree()

def _finaliser_connexion(rep):
    session.update({"connecte":True,"nom":rep["nom"],"numero":rep["numero"],
        "pays":rep.get("pays",""),"bio":rep.get("bio",""),"couleur":rep.get("couleur","cyan"),
        "statut":rep.get("statut","disponible"),"est_admin":rep.get("est_admin",False),
        "non_lus":rep.get("non_lus",0),"premium":rep.get("premium",False),"a_pin":rep.get("a_pin",False)})
    if session["a_pin"]:
        tentatives=0
        while tentatives<3:
            pin=input(f"\n{J}🔢 Code PIN requis: {Z}").strip()
            envoyer_cli({"action":"verifier_pin","pin":pin}); rep_pin=attendre()
            if rep_pin and rep_pin.get("ok"): break
            erreur("PIN incorrect."); tentatives+=1
        else: erreur("Trop de tentatives."); session["connecte"]=False; return
    nl=session["non_lus"]
    print(f"\n{V}{B}✅ Bienvenue {rep['nom']}!{Z}")
    if not session["premium"]: print(f"{J}⛔ Compte non active. Va dans le menu p pour t'abonner.{Z}")
    elif nl>0: print(f"{J}📬 {nl} message(s) non lu(s)!{Z}")
    time.sleep(1)

def menu_messages():
    """Liste les conversations recentes + option nouvelle conversation."""
    while True:
        titre("💬 MESSAGES")
        C2=get_C()
        envoyer_cli({"action":"mes_conversations"}); rep=attendre(5)
        if rep and rep.get("need_premium"): erreur("Abonne-toi d'abord!"); entree(); return
        convs=rep.get("conversations",[]) if rep and rep.get("ok") else []
        if convs:
            print(f"{B}Conversations recentes:{Z}\n")
            for i,c in enumerate(convs,1):
                badge=f" {R}[{c['non_lus']}]{Z}" if c['non_lus']>0 else ""
                print(f"  {C2}{i}{Z} — {c['nom']}{G} ({c['numero']}){Z}{badge}")
                print(f"     {G}{c['dernier_msg'][:35]}...  {c['heure']}{Z}" if len(c['dernier_msg'])>35 else f"     {G}{c['dernier_msg']}  {c['heure']}{Z}")
            print()
        print(f"  {C2}n{Z} — ✏️   Nouvelle conversation (entrer un numero)")
        print(f"  {C2}r{Z} — 🔙  Retour\n")
        choix=input(f"{J}Choix: {Z}").strip().lower()
        if choix=="r": break
        elif choix=="n":
            nd=input("Numero du destinataire: ").strip()
            if nd: _ouvrir_chat(nd)
        elif choix.isdigit():
            idx=int(choix)-1
            if 0<=idx<len(convs): _ouvrir_chat(convs[idx]["numero"])

def _ouvrir_chat(nd):
    envoyer_cli({"action":"chercher","numero":nd}); rep=attendre()
    if not rep or not rep.get("ok"): erreur(rep.get("msg","Introuvable.") if rep else "?"); entree(); return
    u=rep["user"]; st=STATUTS_ICONS.get(u.get("statut","disponible"),""); dc=u.get("derniere_connexion")
    envoyer_cli({"action":"historique","avec":nd,"limite":20}); rep_h=attendre(5)
    if rep_h and rep_h.get("ok"):
        hist=rep_h.get("historique",[])
        if hist:
            print(f"\n{G}── Historique recent ──────────────{Z}")
            for msg in hist:
                dt=msg.get("heure","")[:16].replace("T"," ")
                moi=msg.get("de")==session["numero"]
                col=get_C() if moi else V
                nom_s="[Toi]" if moi else f"[{msg.get('nom_de','?')}]"
                lu=" ✓✓" if (moi and msg.get("lu")) else (" ✓" if moi else "")
                texte=msg.get("texte","")
                reply=msg.get("reply_to")
                if msg.get("chiffre") and msg.get("type")!="fichier":
                    texte=dechiffrer(texte,generer_cle(session["numero"],nd))+" 🔐"
                if reply: print(f"  {G}↩️  {reply[:30]}{Z}")
                print(f"{G}{dt}{Z} {col}{B}{nom_s}{Z}{lu} {texte}")
    print(f"\n{V}✅ {u['nom']} — {st}{Z}")
    if dc and not u.get("en_ligne"): print(f"{G}   Vu le: {dc}{Z}")
    chiffrer_msgs=False; cle_chat=None
    if input(f"\n{J}Activer chiffrement? (o/n): {Z}").strip().lower()=="o":
        chiffrer_msgs=True; cle_chat=generer_cle(session["numero"],nd); succes("Chiffrement active 🔐")
    dernier_msg_id=None; expire_prochain=None
    print(f"\n{G}exit | /fichier | /vocal | /auto N | /repondre | /reaction | /rechercher | /effacer | /favori{Z}\n")
    while True:
        try: texte=input(f"{B}[→ {u['nom']}] > {Z}").strip()
        except: break
        if texte.lower()=="exit": break
        if not texte: continue
        if texte.startswith("/fichier "): _envoyer_fichier(nd,texte[9:].strip()); continue
        if texte.startswith("/vocal "): _envoyer_vocal(nd,texte[7:].strip()); continue
        if texte.startswith("/auto "):
            try: expire_prochain=int(texte.split()[1]); info(f"Prochain message auto-detruit dans {expire_prochain}s.")
            except: erreur("Usage: /auto 30")
            continue
        if texte=="/repondre":
            if not dernier_msg_id: info("Aucun message a repondre."); continue
            rt=input("Ta reponse: ").strip()
            if not rt: continue
            te=chiffrer(rt,cle_chat) if chiffrer_msgs else rt
            envoyer_cli({"action":"message","dest":nd,"texte":te,"chiffre":chiffrer_msgs,"reply_to":dernier_msg_id})
            rep2=attendre(3)
            if rep2 and rep2.get("ok"): dernier_msg_id=rep2.get("msg_id")
            elif rep2: erreur(rep2.get("msg",""))
            continue
        if texte=="/reaction":
            if not dernier_msg_id: info("Aucun message."); continue
            emoji=input("Reaction (👍❤️😂😮😢): ").strip() or "👍"
            envoyer_cli({"action":"reaction","dest":nd,"msg_id":dernier_msg_id,"emoji":emoji}); attendre(3); continue
        if texte=="/rechercher":
            mot=input("Mot cle: ").strip()
            envoyer_cli({"action":"rechercher_msg","avec":nd,"mot":mot}); rep2=attendre(5)
            if rep2 and rep2.get("ok"):
                res=rep2.get("resultats",[])
                if not res: info("Aucun resultat.")
                else:
                    for m in res: print(f"{G}{m.get('heure','')[:16].replace('T',' ')}{Z} {m.get('texte','')}")
            continue
        if texte=="/effacer":
            envoyer_cli({"action":"effacer_historique","avec":nd}); rep2=attendre()
            if rep2 and rep2.get("ok"): succes("Historique efface.")
            continue
        if texte=="/favori":
            envoyer_cli({"action":"ajouter_favori","numero":nd}); rep2=attendre()
            if rep2 and rep2.get("ok"): succes(rep2.get("msg","Ajoute!"))
            continue
        envoyer_cli({"action":"typing","dest":nd,"actif":True})
        te=chiffrer(texte,cle_chat) if chiffrer_msgs else texte
        paquet={"action":"message","dest":nd,"texte":te,"chiffre":chiffrer_msgs}
        if expire_prochain:
            paquet["expire_secondes"]=expire_prochain
            print(f"{G}  ⏱️  Auto-destruction dans {expire_prochain}s{Z}")
            expire_prochain=None
        envoyer_cli(paquet); envoyer_cli({"action":"typing","dest":nd,"actif":False})
        rep2=attendre(3)
        if rep2 and rep2.get("ok"): dernier_msg_id=rep2.get("msg_id")
        elif rep2 and not rep2.get("ok"): erreur(rep2.get("msg",""))
        envoyer_cli({"action":"marquer_lu","avec":nd})

def envoyer_fichier_menu():
    titre("📎 ENVOYER UN FICHIER")
    nd=input("Numero du destinataire: ").strip()
    envoyer_cli({"action":"chercher","numero":nd}); rep=attendre()
    if not rep or not rep.get("ok"): erreur("Introuvable."); entree(); return
    chemin=input("Chemin du fichier: ").strip(); _envoyer_fichier(nd,chemin); entree()

def _envoyer_fichier(nd,chemin):
    chemin=os.path.expanduser(chemin)
    if not os.path.isfile(chemin): erreur(f"Introuvable: {chemin}"); return
    taille=os.path.getsize(chemin)
    if taille>50*1024*1024: erreur("Max 50 MB."); return
    nom_f=os.path.basename(chemin); print(f"{G}📤 Envoi {nom_f} ({fmt(taille)})...{Z}")
    try:
        with open(chemin,"rb") as f: c64=base64.b64encode(f.read()).decode()
    except Exception as e: erreur(f"Lecture: {e}"); return
    envoyer_cli({"action":"envoyer_fichier","dest":nd,"nom_fichier":nom_f,"contenu":c64,"taille":taille})
    rep=attendre(20)
    if rep and rep.get("ok"): succes(rep.get("msg","Envoye!"))
    else: erreur(rep.get("msg","Erreur") if rep else "?")

def _envoyer_vocal(nd,chemin):
    chemin=os.path.expanduser(chemin)
    if not os.path.isfile(chemin): erreur(f"Introuvable: {chemin}"); return
    taille=os.path.getsize(chemin)
    if taille>50*1024*1024: erreur("Max 50 MB."); return
    print(f"{G}🎙️  Envoi du vocal ({fmt(taille)})...{Z}")
    try:
        with open(chemin,"rb") as f: c64=base64.b64encode(f.read()).decode()
    except Exception as e: erreur(f"Lecture: {e}"); return
    envoyer_cli({"action":"envoyer_vocal","dest":nd,"contenu":c64,"taille":taille,"duree":0})
    rep=attendre(20)
    if rep and rep.get("ok"): succes(rep.get("msg","Vocal envoye!"))
    else: erreur(rep.get("msg","Erreur") if rep else "?")

def voir_favoris():
    titre("⭐ CONTACTS FAVORIS"); envoyer_cli({"action":"mes_favoris"}); rep=attendre()
    if not rep or not rep.get("ok"): erreur("Erreur."); entree(); return
    favoris=rep.get("favoris",[])
    if not favoris: info("Aucun favori.")
    else:
        for f in favoris:
            st=STATUTS_ICONS.get(f.get("statut","disponible"),"")
            print(f"  ⭐ {f['nom']}  {G}{f['numero']}{Z}  {st}")
    entree()

def menu_groupes():
    while True:
        titre("👥 GROUPES"); C2=get_C()
        print(f"  {C2}1{Z} — 📋  Mes groupes")
        print(f"  {C2}2{Z} — ➕  Creer un groupe")
        print(f"  {C2}3{Z} — 💬  Entrer dans un groupe")
        print(f"  {C2}4{Z} — 👤  Ajouter un membre")
        print(f"  {C2}r{Z} — 🔙  Retour\n")
        choix=input(f"{J}Choix: {Z}").strip().lower()
        if choix=="1":
            envoyer_cli({"action":"mes_groupes"}); rep=attendre(); titre("📋 MES GROUPES")
            if not rep or not rep.get("ok"): erreur("Erreur."); entree(); continue
            groupes=rep.get("groupes",[])
            if not groupes: info("Aucun groupe.")
            else:
                for g in groupes:
                    adm=f" {J}[Admin]{Z}" if g.get("createur") else ""
                    pin=" 📌" if g.get("epingle") else ""
                    print(f"  • {g['nom']}{adm}{pin}  {G}{g['membres']} membres — ID:{g['id']}{Z}")
            entree()
        elif choix=="2":
            titre("➕ CREER UN GROUPE"); nom=input("Nom du groupe: ").strip()
            if not nom: continue
            envoyer_cli({"action":"creer_groupe","nom":nom}); rep=attendre()
            if rep and rep.get("ok"): succes(f"Groupe '{nom}' cree!"); print(f"   {G}ID: {rep['id_groupe']}{Z}")
            else: erreur(rep.get("msg","?") if rep else "?")
            entree()
        elif choix=="3":
            id_g=input("ID du groupe: ").strip()
            if not id_g: continue
            reply_id=None
            print(f"\n{G}exit | /epingler | /repondre{Z}\n")
            while True:
                try: texte=input(f"{B}[Groupe] > {Z}").strip()
                except: break
                if texte.lower()=="exit": break
                if not texte: continue
                if texte=="/epingler":
                    msg=input("Message a epingler: ").strip()
                    envoyer_cli({"action":"epingler_groupe","id_groupe":id_g,"texte":msg}); attendre(3); continue
                if texte=="/repondre":
                    rt=input("Repondre a (texte): ").strip(); reply_id=rt; info(f"Tu repondras a: {rt[:30]}"); continue
                envoyer_cli({"action":"msg_groupe","id_groupe":id_g,"texte":texte,"reply_to":reply_id}); reply_id=None
                rep=attendre(3)
                if rep and not rep.get("ok"): erreur(rep.get("msg",""))
        elif choix=="4":
            id_g=input("ID du groupe: ").strip(); numero=input("Numero du membre: ").strip()
            envoyer_cli({"action":"ajouter_groupe","id_groupe":id_g,"numero":numero}); rep=attendre()
            if rep and rep.get("ok"): succes(rep.get("msg","Ajoute!"))
            else: erreur(rep.get("msg","?") if rep else "?")
            entree()
        elif choix=="r": break

def menu_canaux():
    while True:
        titre("📡 CANAUX PUBLICS"); C2=get_C()
        print(f"  {C2}1{Z} — 📋  Liste des canaux")
        print(f"  {C2}2{Z} — ➕  Creer un canal")
        print(f"  {C2}3{Z} — 💬  Rejoindre / entrer")
        print(f"  {C2}r{Z} — 🔙  Retour\n")
        choix=input(f"{J}Choix: {Z}").strip().lower()
        if choix=="1":
            titre("📋 CANAUX"); envoyer_cli({"action":"lister_canaux"}); rep=attendre()
            if not rep or not rep.get("ok"): erreur("Erreur."); entree(); continue
            canaux=rep.get("canaux",[])
            if not canaux: info("Aucun canal.")
            else:
                for c in canaux:
                    print(f"  📡 {B}{c['nom']}{Z}  {G}({c['membres']} membres) — par {c['createur']}{Z}")
                    if c.get("description"): print(f"     {G}{c['description']}{Z}")
                    print(f"     {G}ID: {c['id']}{Z}")
            entree()
        elif choix=="2":
            nom=input("Nom du canal: ").strip()
            if not nom: continue
            desc=input("Description (optionnel): ").strip()
            envoyer_cli({"action":"creer_canal","nom":nom,"description":desc}); rep=attendre()
            if rep and rep.get("ok"): succes(f"Canal '{nom}' cree!"); print(f"   {G}ID: {rep['id_canal']}{Z}")
            else: erreur(rep.get("msg","?") if rep else "?")
            entree()
        elif choix=="3":
            id_c=input("ID du canal: ").strip()
            if not id_c: continue
            envoyer_cli({"action":"rejoindre_canal","id_canal":id_c}); rep=attendre()
            if not rep or not rep.get("ok"): erreur(rep.get("msg","Canal introuvable.") if rep else "?"); entree(); continue
            succes(f"Tu as rejoint '{rep['nom']}'!")
            envoyer_cli({"action":"hist_canal","id_canal":id_c}); rep_h=attendre(5)
            if rep_h and rep_h.get("ok"):
                for m in rep_h.get("historique",[]): print(f"{G}{m.get('heure','')[:16].replace('T',' ')}{Z} [{m.get('nom','?')}] {m.get('texte','')}")
            print(f"\n{G}exit = retour{Z}\n")
            while True:
                try: texte=input(f"{B}[Canal] > {Z}").strip()
                except: break
                if texte.lower()=="exit": break
                if not texte: continue
                envoyer_cli({"action":"msg_canal","id_canal":id_c,"texte":texte}); rep=attendre(3)
                if rep and not rep.get("ok"): erreur(rep.get("msg",""))
        elif choix=="r": break

def menu_premium():
    titre("💰 ABONNEMENT TERMCHAT")
    envoyer_cli({"action":"info_premium"}); rep=attendre()
    if not rep or not rep.get("ok"): erreur("Erreur."); entree(); return
    est_prem=rep.get("premium",False); expire=rep.get("premium_expire"); wave=rep.get("wave",""); prix=rep.get("prix","1500 FCFA"); jours=rep.get("duree_jours",60)
    if est_prem and expire:
        expire_str=datetime.datetime.fromtimestamp(expire).strftime("%d/%m/%Y")
        print(f"{J}{B}⭐ Ton abonnement est ACTIF jusqu'au {expire_str}!{Z}"); entree(); return
    print(f"{R}{B}⛔ Compte non active — abonne-toi pour tout debloquer{Z}\n")
    print(f"{B}Comment s'abonner:{Z}\n")
    print(f"  1️⃣  Envoie {prix} sur Wave au: {get_C()}{wave}{Z}")
    print(f"  2️⃣  Note le code de transaction recu par SMS")
    print(f"  3️⃣  Entre le code ci-dessous\n")
    print(f"{J}Duree: {jours} jours | Prix: {prix}{Z}\n")
    if input(f"{J}Tu as deja paye? Entrer le code (o/n): {Z}").strip().lower()!="o": entree(); return
    code=input(f"{B}Code de transaction: {Z}").strip()
    if not code: erreur("Code requis."); entree(); return
    envoyer_cli({"action":"demander_premium","code":code}); rep=attendre(5)
    if rep and rep.get("ok"): succes(rep["msg"]); print(f"{G}L'administrateur va verifier et confirmer sous peu.{Z}")
    else: erreur(rep.get("msg","?") if rep else "?")
    entree()

def chercher_user():
    titre("🔍 CHERCHER UN UTILISATEUR"); numero=input("Numero: ").strip()
    envoyer_cli({"action":"chercher","numero":numero}); rep=attendre()
    if rep and rep.get("ok"):
        u=rep["user"]; st=STATUTS_ICONS.get(u.get("statut","disponible"),""); dc=u.get("derniere_connexion")
        prem=f"  {J}⭐ Abonne{Z}" if u.get("premium") else ""
        print(f"\n  👤 {u['nom']}  📱 {u['numero']} {V}✓{Z}{prem}")
        print(f"  🌍 {u.get('pays','—')}  📝 {u.get('bio','—')}")
        print(f"  {st}")
        if dc and not u.get("en_ligne"): print(f"  {G}Vu le: {dc}{Z}")
    else: erreur(rep.get("msg","Introuvable.") if rep else "?")
    entree()

def voir_en_ligne():
    titre("🌐 UTILISATEURS EN LIGNE"); envoyer_cli({"action":"en_ligne"}); rep=attendre()
    if not rep or not rep.get("ok"): erreur("Erreur."); entree(); return
    users=rep.get("users",[])
    if not users: info("Personne d'autre en ligne.")
    else:
        print(f"{V}  {len(users)} en ligne:{Z}\n")
        for u in users:
            st=STATUTS_ICONS.get(u.get("statut","disponible"),"")
            print(f"  🟢  {u['nom']}  {G}{u['numero']}{Z}  {st}")
    entree()

def mon_profil():
    titre("👤 MON PROFIL"); st=STATUTS_ICONS.get(session.get("statut","disponible"),"")
    print(f"  👤  Nom:    {B}{session.get('nom','')}{Z}")
    print(f"  📱  N°:     {session.get('numero','')} {V}✓{Z}")
    print(f"  🌍  Pays:   {G}{session.get('pays','—')}{Z}")
    print(f"  📝  Bio:    {G}{session.get('bio','—')}{Z}")
    print(f"  😊  Statut: {st}")
    if session.get("premium"): print(f"  ⭐  {J}Compte Abonne{Z}")
    print()
    if input("Modifier ta bio? (o/n): ").strip().lower()=="o":
        bio=input("Nouvelle bio (max 150): ").strip()[:150]
        envoyer_cli({"action":"modifier_bio","bio":bio}); rep=attendre()
        if rep and rep.get("ok"): session["bio"]=bio; succes(rep["msg"])
        else: erreur(rep.get("msg","?") if rep else "?")
    entree()

def changer_statut():
    titre("😊 CHANGER MON STATUT")
    statuts=[("disponible","🟢 Disponible"),("occupe","🟡 Occupe"),("ne_pas_deranger","🔴 Ne pas deranger"),("absent","⚫ Absent")]
    for i,(s,label) in enumerate(statuts,1): print(f"  {i} — {label}")
    choix=input("\nChoix: ").strip()
    try:
        statut=statuts[int(choix)-1][0]
        envoyer_cli({"action":"changer_statut","statut":statut}); rep=attendre()
        if rep and rep.get("ok"): session["statut"]=statut; succes(rep["msg"])
        else: erreur(rep.get("msg","?") if rep else "?")
    except: erreur("Choix invalide.")
    entree()

def personnalisation():
    titre("🎨 PERSONNALISATION"); couleurs=list(COULEURS.items())
    for i,(nom_c,code) in enumerate(couleurs,1): print(f"  {code}{B}{i}{Z} — {code}{nom_c}{Z}")
    choix=input(f"\nChoix (1-{len(couleurs)}): ").strip()
    try:
        nom_c,_=couleurs[int(choix)-1]
        envoyer_cli({"action":"changer_couleur","couleur":nom_c}); rep=attendre()
        if rep and rep.get("ok"): session["couleur"]=nom_c; succes(f"Couleur → {nom_c}!")
        else: erreur(rep.get("msg","?") if rep else "?")
    except: erreur("Choix invalide.")
    entree()

def menu_securite():
    while True:
        titre("🛡️  SECURITE"); C2=get_C()
        print(f"  {C2}1{Z} — 🔑  Changer mot de passe")
        print(f"  {C2}2{Z} — 🚫  Bloquer un utilisateur")
        print(f"  {C2}3{Z} — ✅  Debloquer un utilisateur")
        print(f"  {C2}4{Z} — 🔢  Code PIN")
        print(f"  {C2}5{Z} — 🗑️   Supprimer mon compte")
        print(f"  {C2}r{Z} — 🔙  Retour\n")
        choix=input(f"{J}Choix: {Z}").strip().lower()
        if choix=="1":
            titre("🔑 CHANGER MOT DE PASSE")
            ancien=input("Ancien mdp: ").strip(); nouveau=input("Nouveau mdp: ").strip(); confirm=input("Confirmer: ").strip()
            if nouveau!=confirm: erreur("Ne correspondent pas."); entree(); continue
            if len(nouveau)<4: erreur("Min 4 caracteres."); entree(); continue
            envoyer_cli({"action":"changer_mdp","ancien":ancien,"nouveau":nouveau}); rep=attendre()
            if rep and rep.get("ok"): succes(rep["msg"])
            else: erreur(rep.get("msg","?") if rep else "?")
            entree()
        elif choix=="2":
            numero=input("Numero a bloquer: ").strip()
            envoyer_cli({"action":"bloquer","numero":numero,"bloquer":True}); rep=attendre()
            if rep and rep.get("ok"): succes(rep["msg"])
            else: erreur(rep.get("msg","?") if rep else "?")
            entree()
        elif choix=="3":
            numero=input("Numero a debloquer: ").strip()
            envoyer_cli({"action":"bloquer","numero":numero,"bloquer":False}); rep=attendre()
            if rep and rep.get("ok"): succes(rep["msg"])
            else: erreur(rep.get("msg","?") if rep else "?")
            entree()
        elif choix=="4":
            titre("🔢 CODE PIN")
            print("  1 — Activer / changer le PIN"); print("  2 — Desactiver le PIN")
            c2=input("\nChoix: ").strip()
            if c2=="1":
                pin=input("Nouveau PIN (4 chiffres): ").strip(); pin2=input("Confirmer: ").strip()
                if pin!=pin2: erreur("Les PIN ne correspondent pas."); entree(); continue
                envoyer_cli({"action":"definir_pin","pin":pin}); rep=attendre()
                if rep and rep.get("ok"): session["a_pin"]=True; succes(rep["msg"])
                else: erreur(rep.get("msg","?") if rep else "?")
            elif c2=="2":
                envoyer_cli({"action":"supprimer_pin"}); rep=attendre()
                if rep and rep.get("ok"): session["a_pin"]=False; succes(rep["msg"])
                else: erreur(rep.get("msg","?") if rep else "?")
            entree()
        elif choix=="5":
            titre("🗑️  SUPPRIMER MON COMPTE"); print(f"{R}{B}⚠️  Action irreversible!{Z}\n")
            if input("Tape 'SUPPRIMER': ").strip()!="SUPPRIMER": info("Annule."); entree(); continue
            mdp=input("Mot de passe: ").strip()
            envoyer_cli({"action":"supprimer_compte","mdp":mdp}); rep=attendre()
            if rep and rep.get("ok"):
                succes("Compte supprime."); session["connecte"]=False; session["nom"]=None; session["numero"]=None; entree(); break
            else: erreur(rep.get("msg","?") if rep else "?"); entree()
        elif choix=="r": break

def panel_admin():
    if not session.get("est_admin"):
        titre("⚙️  ACCES ADMIN"); code=input("Code admin: ").strip()
        envoyer_cli({"action":"admin_login","code":code}); rep=attendre()
        if not rep or not rep.get("ok"): erreur(rep.get("msg","Code incorrect.") if rep else "?"); entree(); return
        session["est_admin"]=True; succes("Acces accorde!")
    while True:
        titre("⚙️  PANEL ADMIN"); C2=get_C()
        print(f"  {C2}1{Z} — 📊  Statistiques")
        print(f"  {C2}2{Z} — 👥  Tous les utilisateurs")
        print(f"  {C2}3{Z} — 📢  Broadcast")
        print(f"  {C2}4{Z} — ⛔  Kick utilisateur")
        print(f"  {C2}p{Z} — 💰  Demandes Premium")
        print(f"  {C2}r{Z} — 🔙  Retour\n")
        choix=input(f"{J}Choix: {Z}").strip().lower()
        if choix=="1":
            envoyer_cli({"action":"admin_stats"}); rep=attendre()
            if rep and rep.get("ok"):
                s=rep["stats"]; titre("📊 STATISTIQUES")
                print(f"  👤 Utilisateurs  : {B}{s.get('utilisateurs',0)}{Z}")
                print(f"  🟢 En ligne      : {B}{s.get('en_ligne',0)}{Z}")
                print(f"  💬 Messages      : {B}{s.get('messages_total',0)}{Z}")
                print(f"  📎 Fichiers      : {B}{s.get('fichiers_total',0)}{Z}")
                print(f"  📝 Inscriptions  : {B}{s.get('inscriptions_total',0)}{Z}")
                print(f"  👥 Groupes       : {B}{s.get('groupes',0)}{Z}")
                print(f"  📡 Canaux        : {B}{s.get('canaux',0)}{Z}")
                print(f"  💭 Conversations : {B}{s.get('conversations',0)}{Z}")
            else: erreur("Erreur.")
            entree()
        elif choix=="2":
            envoyer_cli({"action":"admin_users"}); rep=attendre(8)
            if rep and rep.get("ok"):
                titre("👥 UTILISATEURS")
                for u in rep.get("users",[]):
                    st=f"{V}🟢{Z}" if u.get("en_ligne") else f"{G}⚫{Z}"
                    prem=f" {J}⭐{Z}" if u.get("premium") else f" {R}⛔{Z}"
                    print(f"  {st} {u['nom']:<12} {u['numero']}  {G}{u.get('pays','')}{Z}{prem}")
                    print(f"     {G}Inscrit:{u.get('inscription','')}  Vu:{u.get('derniere_connexion','—')}{Z}")
            else: erreur("Erreur.")
            entree()
        elif choix=="3":
            msg=input("Message: ").strip()
            if not msg: continue
            envoyer_cli({"action":"admin_broadcast","msg":msg}); rep=attendre()
            if rep and rep.get("ok"): succes(rep.get("msg","Envoye!"))
            entree()
        elif choix=="4":
            numero=input("Numero a kick: ").strip()
            envoyer_cli({"action":"admin_kick","numero":numero}); rep=attendre()
            if rep and rep.get("ok"): succes(rep.get("msg",""))
            else: erreur(rep.get("msg","?") if rep else "?")
            entree()
        elif choix=="p":
            titre("💰 DEMANDES EN ATTENTE"); envoyer_cli({"action":"demandes_premium"}); rep=attendre(5)
            if not rep or not rep.get("ok"): erreur("Erreur."); entree(); continue
            demandes=rep.get("demandes",[])
            if not demandes: info("Aucune demande en attente."); entree(); continue
            for i,d in enumerate(demandes,1):
                print(f"\n  {J}{B}{i}. {d['nom']} — {d['numero']}{Z}")
                print(f"     🔑 Code: {d['code']}")
                print(f"     🕐 Heure: {d['heure'][:16].replace('T',' ')}")
            print()
            numero=input("Numero a confirmer (ou 'r' = retour): ").strip()
            if numero.lower()=="r": continue
            action=input(f"  {V}c{Z} = Confirmer  |  {R}x{Z} = Rejeter: ").strip().lower()
            if action=="c":
                envoyer_cli({"action":"confirmer_premium","numero":numero}); rep=attendre(5)
                if rep and rep.get("ok"): succes(rep["msg"])
                else: erreur(rep.get("msg","?") if rep else "?")
            elif action=="x":
                envoyer_cli({"action":"rejeter_premium","numero":numero}); rep=attendre(5)
                if rep and rep.get("ok"): succes("Demande rejetee.")
                else: erreur(rep.get("msg","?") if rep else "?")
            entree()
        elif choix=="r": break

def quitter(sig=None,frame=None):
    en_cours=False
    if session.get("connecte"):
        try: envoyer_cli({"action":"deconnecter"})
        except Exception: pass
    try: sock_cli.close()
    except Exception: pass
    print(f"\n{get_C()}{B}A bientot! 👋{Z}\n"); sys.exit(0)

def main():
    global sock_cli,en_cours
    banniere()
    host=sys.argv[1] if len(sys.argv)>=2 else "junction.proxy.rlwy.net"
    port=int(sys.argv[2]) if len(sys.argv)>=3 else 35030
    print(f"{G}🔌 Connexion a {host}:{port}...{Z}")
    try:
        sock_cli=socket.socket(socket.AF_INET,socket.SOCK_STREAM)
        sock_cli.settimeout(10); sock_cli.connect((host,port)); sock_cli.settimeout(None)
        succes("Connecte!"); print(f"{G}   📥 Fichiers → ~/termchat_downloads/{Z}\n")
    except Exception as e: erreur(f"Impossible de se connecter: {e}"); sys.exit(1)
    threading.Thread(target=recevoir,daemon=True).start()
    signal.signal(signal.SIGINT,quitter)
    try: signal.signal(signal.SIGTERM,quitter)
    except Exception: pass
    time.sleep(0.3)
    try:
        while en_cours:
            if not session["connecte"]:
                choix=menu_accueil()
                if choix=="1": inscrire()
                elif choix=="2": connecter()
                elif choix=="3": connecter_par_numero()
                elif choix=="q": quitter()
            else:
                choix=menu_principal()
                if not session.get("premium"):
                    if choix=="p": menu_premium()
                    elif choix=="s": menu_securite()
                    elif choix=="q": quitter()
                else:
                    if choix=="1": menu_messages()
                    elif choix=="2": menu_groupes()
                    elif choix=="3": voir_favoris()
                    elif choix=="4": envoyer_fichier_menu()
                    elif choix=="5": chercher_user()
                    elif choix=="6": voir_en_ligne()
                    elif choix=="7": mon_profil()
                    elif choix=="8": changer_statut()
                    elif choix=="9": personnalisation()
                    elif choix=="c": menu_canaux()
                    elif choix=="p": menu_premium()
                    elif choix=="s": menu_securite()
                    elif choix=="0": panel_admin()
                    elif choix=="q": quitter()
    except KeyboardInterrupt: quitter()

if __name__=="__main__": main()
