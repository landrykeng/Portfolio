from datetime import date
from pathlib import Path

import numpy as np
import pandas as pd
import streamlit as st
from streamlit_echarts import JsCode, st_echarts

# ───────────────────────── Configuration ─────────────────────────
APP_NAME = "My portfolio"
DATA_FILE = Path("data/my_portfolio.xlsx")
COLS = ["ID", "Date", "Nature", "Catégorie", "Date échéance", "Libellé", "Montant"]
DEFAULT_CATS = ["Transport", "Alimentation", "Connexion", "Emprunt", "Prêt", "Aide",
                "Fourniture", "Service", "Bien de base", "Salaire", "Autre"]
CAT_EMPRUNT = {"emprunt"}
CAT_PRET = {"prêt", "pret"}
CAT_FIN = CAT_EMPRUNT | CAT_PRET
MOIS = ["janv.", "févr.", "mars", "avr.", "mai", "juin",
        "juil.", "août", "sept.", "oct.", "nov.", "déc."]

C_RES, C_DEP, C_NET = "#0E7C66", "#E5484D", "#3B5BDB"
C_GOLD, C_MUTED, C_PREV = "#C48A1A", "#8A96AB", "#B8C2D6"

AX_FMT = JsCode("function(v){var a=Math.abs(v);"
                "if(a>=1000000){return (v/1000000)+' M'}"
                "if(a>=1000){return (v/1000)+' k'}return v}").js_code
TIP_FMT = JsCode("function(v){return Number(v).toLocaleString('fr-FR')+' FCFA'}").js_code

st.set_page_config(page_title=APP_NAME, page_icon=":material/account_balance_wallet:",
                   layout="wide")

st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Plus+Jakarta+Sans:wght@400;500;600;700;800&display=swap');
html, body, .stApp, .stApp p, .stApp h1, .stApp h2, .stApp h3, .stApp h4, .stApp h5,
.stApp label, .stApp button, .stApp input, .stApp textarea, .stApp li,
[data-testid="stMetricValue"], [data-testid="stMetricLabel"] {
    font-family: 'Plus Jakarta Sans', sans-serif;
}
span[data-testid="stIconMaterial"] { font-family: "Material Symbols Rounded" !important; }
.block-container { padding-top: 2.2rem; max-width: 1280px; }
h1 { font-weight: 800 !important; letter-spacing: -0.03em; }
h5 { font-weight: 700 !important; margin-bottom: .4rem; }
[data-testid="stVerticalBlockBorderWrapper"] {
    background: #fff; border: 1px solid #E3E8F0 !important; border-radius: 18px;
    box-shadow: 0 1px 2px rgba(22,32,47,.04);
}
[data-testid="stMetricValue"] { font-size: 1.9rem; font-weight: 800; letter-spacing: -0.02em; }
[data-testid="stMetricLabel"] { font-weight: 600; color: #5B677B; }
.stTabs [data-baseweb="tab"] { font-weight: 600; }
.stTabs [data-baseweb="tab-list"] { gap: .6rem; }
</style>
""", unsafe_allow_html=True)


# ───────────────────────── Données (Excel) ─────────────────────────
def save(ops: pd.DataFrame, cats: list[str]) -> None:
    DATA_FILE.parent.mkdir(parents=True, exist_ok=True)
    with pd.ExcelWriter(DATA_FILE, engine="openpyxl",
                        date_format="DD/MM/YYYY", datetime_format="DD/MM/YYYY") as w:
        ops[COLS].to_excel(w, sheet_name="Operations", index=False)
        pd.DataFrame({"Catégorie": cats}).to_excel(w, sheet_name="Categories", index=False)


def load() -> tuple[pd.DataFrame, list[str]]:
    if not DATA_FILE.exists():
        save(pd.DataFrame(columns=COLS), DEFAULT_CATS)
    ops = pd.read_excel(DATA_FILE, sheet_name="Operations")
    cats = pd.read_excel(DATA_FILE, sheet_name="Categories")["Catégorie"].dropna().astype(str).tolist()
    ops["ID"] = pd.to_numeric(ops["ID"], errors="coerce").fillna(0).astype(int)
    ops["Date"] = pd.to_datetime(ops["Date"], errors="coerce")
    ops["Date échéance"] = pd.to_datetime(ops["Date échéance"], errors="coerce")
    ops["Montant"] = pd.to_numeric(ops["Montant"], errors="coerce").fillna(0.0)
    ops["Catégorie"] = ops["Catégorie"].astype(str)
    ops["Libellé"] = ops["Libellé"].astype(str)
    return ops.dropna(subset=["Date"]).reset_index(drop=True), cats


def flash(msg: str) -> None:
    st.session_state["flash"] = msg


# ───────────────────────── Utilitaires ─────────────────────────
def fcfa(x: float, signed: bool = False) -> str:
    s = f"{abs(x):,.0f}".replace(",", "\u202f")
    sign = "-" if x < 0 else ("+" if signed else "")
    return f"{sign}{s} FCFA"


def ml(p: pd.Period) -> str:
    return f"{MOIS[p.month - 1]} {p.year}"


def pct_delta(cur: float, prev: float, label: str = "vs mois précédent"):
    """Variation en %, et couleur forcée si le calcul est impossible."""
    if prev == 0:
        return "Pas de base de comparaison", "off"
    v = (cur - prev) / abs(prev) * 100
    return f"{v:+.1f} %".replace(".", ",") + f" {label}", None


def total(d: pd.DataFrame, nature: str, only=None, skip=None) -> float:
    x = d[d["Nature"] == nature]
    low = x["Catégorie"].str.lower()
    if only:
        x = x[low.isin(only)]
    elif skip:
        x = x[~low.isin(skip)]
    return float(x["Montant"].sum())


def monthly(d: pd.DataFrame, months: pd.PeriodIndex) -> pd.DataFrame:
    g = d.groupby([d["Date"].dt.to_period("M"), "Nature"])["Montant"].sum().unstack(fill_value=0)
    g = g.reindex(months, fill_value=0)
    for c in ("Dépense", "Ressource"):
        if c not in g:
            g[c] = 0.0
    return g


def prepare(ops: pd.DataFrame):
    today = pd.Timestamp.today().normalize()
    done = ops[ops["Date"] <= today]
    if done.empty:
        st.info("Aucune opération à date. Ajoutez-en depuis l'onglet Enregistrer.")
        return None
    cur = today.to_period("M")
    months = pd.period_range(done["Date"].min().to_period("M"), cur, freq="M")
    return today, done, cur, months


def card_title(text: str, icon: str) -> None:
    st.markdown(f"##### :material/{icon}: {text}")


def kpi(col, label, value, delta=None, color=None):
    with col, st.container(border=True):
        kw = {"delta": delta} if delta else {}
        if color:
            kw["delta_color"] = color
        st.metric(label, value, **kw)


def style_axes():
    return dict(
        xAxis={"type": "category", "axisLine": {"lineStyle": {"color": "#CBD3E1"}},
               "axisLabel": {"color": C_MUTED}, "axisTick": {"show": False}},
        yAxis={"type": "value", "splitLine": {"lineStyle": {"color": "#E9EDF4"}},
               "axisLabel": {"color": C_MUTED, "formatter": AX_FMT}},
    )


def base_option(x, series, colors, legend=True):
    ax = style_axes()
    ax["xAxis"]["data"] = x
    opt = {"color": colors, "tooltip": {"trigger": "axis", "valueFormatter": TIP_FMT,
                                        "axisPointer": {"type": "shadow"}},
           "grid": {"left": 8, "right": 16, "top": 44, "bottom": 8, "containLabel": True},
           "series": series, **ax}
    if legend:
        opt["legend"] = {"top": 0, "right": 0, "icon": "roundRect", "itemWidth": 14,
                         "textStyle": {"color": "#16202F", "fontWeight": 600}}
    return opt


# ───────────────────────── Onglet 1 : Enregistrer ─────────────────────────
def tab_saisie(ops: pd.DataFrame, cats: list[str]) -> pd.DataFrame:
    left, right = st.columns([2, 3], gap="large")
    with left, st.container(border=True):
        card_title("Nouvelle opération", "edit_note")
        with st.form("saisie", clear_on_submit=True, border=False):
            c1, c2 = st.columns(2)
            d = c1.date_input("Date", value=date.today(), format="DD/MM/YYYY")
            nature = c2.radio("Nature", ["Dépense", "Ressource"], horizontal=True)
            c3, c4 = st.columns(2)
            cat = c3.selectbox("Catégorie", cats)
            ech = c4.date_input("Date d'échéance (facultative)", value=None, format="DD/MM/YYYY")
            lib = st.text_input("Libellé", placeholder="Ex. : Recharge internet, loyer, salaire…")
            mnt = st.number_input("Montant (FCFA)", min_value=0.0, step=500.0, format="%.0f")
            ok = st.form_submit_button("Enregistrer", type="primary", icon=":material/save:",
                                       width="stretch")
        if ok:
            if not lib.strip() or mnt <= 0 or cat is None:
                st.error("Renseignez un libellé, une catégorie et un montant supérieur à 0.")
            else:
                new = pd.DataFrame([{
                    "ID": (int(ops["ID"].max()) + 1) if not ops.empty else 1,
                    "Date": pd.Timestamp(d), "Nature": nature, "Catégorie": cat,
                    "Date échéance": pd.Timestamp(ech) if ech else pd.NaT,
                    "Libellé": lib.strip(), "Montant": float(mnt)}])
                ops = new if ops.empty else pd.concat([ops, new], ignore_index=True)
                save(ops, cats)
                st.toast("Opération enregistrée", icon=":material/check_circle:")

    with right, st.container(border=True):
        card_title("Dernières saisies", "history")
        if ops.empty:
            st.caption("Rien à afficher pour le moment.")
        else:
            r = ops.sort_values(["Date", "ID"], ascending=False).head(12)
            st.dataframe(pd.DataFrame({
                "Date": r["Date"].dt.strftime("%d/%m/%Y"), "Nature": r["Nature"],
                "Catégorie": r["Catégorie"], "Libellé": r["Libellé"],
                "Montant": r["Montant"].map(fcfa)}), hide_index=True, width="stretch")
    return ops


# ───────────────────────── Tableau de bord : vue d'ensemble ─────────────────────────
def view_overview(ops: pd.DataFrame):
    p = prepare(ops)
    if p is None:
        return
    today, done, cur, months = p
    prev = cur - 1
    m = monthly(done, months)
    dep, res = m["Dépense"], m["Ressource"]
    tot_dep, tot_res = float(dep.sum()), float(res.sum())
    solde = tot_res - tot_dep
    solde_prev = float((res - dep)[m.index <= prev].sum())

    k1, k2, k3 = st.columns(3)
    t, c = pct_delta(float(dep.get(cur, 0)), float(dep.get(prev, 0)))
    kpi(k1, ":material/trending_down: Total des dépenses", fcfa(tot_dep), t, "off" if c else "inverse")
    t, c = pct_delta(float(res.get(cur, 0)), float(res.get(prev, 0)))
    kpi(k2, ":material/trending_up: Total des ressources", fcfa(tot_res), t, c)
    t, c = pct_delta(solde, solde_prev, f"vs fin {ml(prev)}")
    kpi(k3, ":material/account_balance_wallet: Solde à date", fcfa(solde), t, c)

    with st.container(border=True):
        card_title("Dépenses et ressources dans le temps", "show_chart")
        series = [
            {"name": "Ressources", "type": "line", "smooth": True, "symbolSize": 7,
             "lineStyle": {"width": 3}, "areaStyle": {"opacity": 0.12},
             "data": res.round(0).tolist()},
            {"name": "Dépenses", "type": "line", "smooth": True, "symbolSize": 7,
             "lineStyle": {"width": 3}, "areaStyle": {"opacity": 0.12},
             "data": dep.round(0).tolist()},
        ]
        opt = base_option([ml(x) for x in months], series, [C_RES, C_DEP])
        opt["xAxis"]["boundaryGap"] = False
        opt["tooltip"]["axisPointer"] = {"type": "line"}
        st_echarts(opt, height="340px", key="evolution")

    a, b = st.columns([3, 2], gap="medium")
    with a, st.container(border=True):
        card_title(f"Dépenses par poste : {ml(cur)} et {ml(prev)}", "bar_chart")
        dd = done[done["Nature"] == "Dépense"]
        per = dd["Date"].dt.to_period("M")
        c_cur = dd[per == cur].groupby("Catégorie")["Montant"].sum()
        c_prev = dd[per == prev].groupby("Catégorie")["Montant"].sum()
        order = sorted(set(c_cur.index) | set(c_prev.index),
                       key=lambda k: -(c_cur.get(k, 0) + c_prev.get(k, 0)))
        if not order:
            st.caption("Aucune dépense ce mois ni le mois précédent.")
        else:
            bar = {"type": "bar", "barMaxWidth": 26, "itemStyle": {"borderRadius": [6, 6, 0, 0]}}
            series = [
                {**bar, "name": ml(prev), "data": [float(c_prev.get(k, 0)) for k in order]},
                {**bar, "name": ml(cur), "data": [float(c_cur.get(k, 0)) for k in order]},
            ]
            opt = base_option(order, series, [C_PREV, C_DEP])
            opt["xAxis"]["axisLabel"]["rotate"] = 25 if len(order) > 5 else 0
            st_echarts(opt, height="340px", key="postes")
    with b, st.container(border=True):
        card_title(f"Plus grosses dépenses de {ml(cur)}", "receipt_long")
        top = dd[per == cur].nlargest(6, "Montant")
        if top.empty:
            st.caption("Aucune dépense ce mois.")
        else:
            st.dataframe(pd.DataFrame({
                "Date": top["Date"].dt.strftime("%d/%m"), "Libellé": top["Libellé"],
                "Catégorie": top["Catégorie"], "Montant": top["Montant"].map(fcfa)}),
                hide_index=True, width="stretch")

    a, b = st.columns([3, 2], gap="medium")
    with a, st.container(border=True):
        card_title("Récapitulatif mensuel", "calendar_month")
        rec = pd.DataFrame({"res": res, "dep": dep})
        rec["net"] = rec["res"] - rec["dep"]
        rec["cum"] = rec["net"].cumsum()
        rec = rec.iloc[::-1]
        st.dataframe(pd.DataFrame({
            "Mois": [ml(x) for x in rec.index], "Ressources": rec["res"].map(fcfa),
            "Dépenses": rec["dep"].map(fcfa), "Solde du mois": rec["net"].map(lambda v: fcfa(v, True)),
            "Solde cumulé": rec["cum"].map(fcfa)}), hide_index=True, width="stretch")
    with b, st.container(border=True):
        card_title("Échéances à venir", "event_upcoming")
        up = ops[ops["Date échéance"].notna() & (ops["Date échéance"] >= today)]
        up = up.sort_values("Date échéance").head(8)
        if up.empty:
            st.caption("Aucune échéance à venir.")
        else:
            jours = (up["Date échéance"] - today).dt.days
            st.dataframe(pd.DataFrame({
                "Échéance": up["Date échéance"].dt.strftime("%d/%m/%Y"),
                "Délai": jours.map(lambda j: "Aujourd'hui" if j == 0 else f"Dans {j} j"),
                "Libellé": up["Libellé"], "Nature": up["Nature"],
                "Montant": up["Montant"].map(fcfa)}), hide_index=True, width="stretch")


# ───────────────────────── Tableau de bord : bilan ─────────────────────────
def view_bilan(ops: pd.DataFrame):
    asof = st.date_input("Bilan arrêté au", value=date.today(), format="DD/MM/YYYY", key="bilan_date")
    d = ops[ops["Date"] <= pd.Timestamp(asof)]
    if d.empty:
        st.info("Aucune opération à cette date.")
        return
    treso = total(d, "Ressource") - total(d, "Dépense")
    creances = total(d, "Dépense", only=CAT_PRET) - total(d, "Ressource", only=CAT_PRET)
    dettes = total(d, "Ressource", only=CAT_EMPRUNT) - total(d, "Dépense", only=CAT_EMPRUNT)
    actif, net = treso + creances, treso + creances - dettes

    k1, k2, k3 = st.columns(3)
    kpi(k1, ":material/savings: Total actif", fcfa(actif))
    kpi(k2, ":material/credit_card: Total passif (dettes)", fcfa(dettes))
    kpi(k3, ":material/account_balance: Patrimoine net", fcfa(net))

    a, b = st.columns([2, 3], gap="medium")
    with a, st.container(border=True):
        card_title("Bilan", "balance")
        st.dataframe(pd.DataFrame({
            "Rubrique": ["ACTIF", "Trésorerie disponible", "Créances (prêts accordés)", "Total actif",
                         "PASSIF", "Dettes (emprunts à rembourser)", "Patrimoine net", "Total passif"],
            "Montant": ["", fcfa(treso), fcfa(creances), fcfa(actif), "",
                        fcfa(dettes), fcfa(net), fcfa(dettes + net)]}),
            hide_index=True, width="stretch")
        st.caption("Emprunt : une ressource est de l'argent reçu, une dépense un remboursement. "
                   "Prêt : une dépense est de l'argent prêté, une ressource un remboursement reçu.")
    with b, st.container(border=True):
        card_title("Actif et passif", "stacked_bar_chart")
        def s(name, vals):
            return {"name": name, "type": "bar", "stack": "t", "barMaxWidth": 90, "data": vals}
        series = [s("Trésorerie", [treso, 0]), s("Créances", [creances, 0]),
                  s("Dettes", [0, dettes]), s("Patrimoine net", [0, net])]
        opt = base_option(["Actif", "Passif"], series, [C_NET, C_GOLD, C_DEP, C_RES])
        opt["tooltip"]["trigger"] = "item"
        st_echarts(opt, height="340px", key="bilan")


# ───────────────────────── Tableau de bord : flux de trésorerie ─────────────────────────
def view_flux(ops: pd.DataFrame):
    p = prepare(ops)
    if p is None:
        return
    _, done, cur, months = p
    d = done.copy()
    d["M"] = d["Date"].dt.to_period("M")
    d["fin"] = d["Catégorie"].str.lower().isin(CAT_FIN)
    d["signed"] = np.where(d["Nature"] == "Ressource", d["Montant"], -d["Montant"])

    def agg(mask, col):
        return d[mask].groupby("M")[col].sum().reindex(months, fill_value=0.0)

    enc = agg(~d["fin"] & (d["Nature"] == "Ressource"), "Montant")
    dec = agg(~d["fin"] & (d["Nature"] == "Dépense"), "Montant")
    expl = enc - dec
    fin = agg(d["fin"], "signed")
    net = expl + fin
    close = net.cumsum()
    opening = close - net
    prev = cur - 1

    k1, k2, k3 = st.columns(3)
    t, c = pct_delta(float(expl.get(cur, 0)), float(expl.get(prev, 0)))
    kpi(k1, ":material/storefront: Flux d'exploitation (mois)", fcfa(float(expl.get(cur, 0))), t, c)
    t, c = pct_delta(float(fin.get(cur, 0)), float(fin.get(prev, 0)))
    kpi(k2, ":material/handshake: Flux de financement (mois)", fcfa(float(fin.get(cur, 0))), t, c)
    kpi(k3, ":material/account_balance_wallet: Trésorerie de clôture", fcfa(float(close.iloc[-1])),
        f"{fcfa(float(net.get(cur, 0)), True)} ce mois", None if net.get(cur, 0) != 0 else "off")

    with st.container(border=True):
        card_title("Flux mensuels et trésorerie de clôture", "waterfall_chart")
        bar = {"type": "bar", "barMaxWidth": 28, "itemStyle": {"borderRadius": [5, 5, 0, 0]}}
        series = [
            {**bar, "name": "Exploitation", "data": expl.round(0).tolist()},
            {**bar, "name": "Financement", "data": fin.round(0).tolist()},
            {"name": "Trésorerie de clôture", "type": "line", "smooth": True, "symbolSize": 7,
             "lineStyle": {"width": 3}, "data": close.round(0).tolist()},
        ]
        st_echarts(base_option([ml(x) for x in months], series, [C_NET, C_GOLD, C_RES]),
                   height="340px", key="flux")

    with st.container(border=True):
        card_title("Tableau des flux de trésorerie", "table_chart")
        idx = months[::-1]
        st.dataframe(pd.DataFrame({
            "Mois": [ml(x) for x in idx],
            "Trésorerie d'ouverture": opening[idx].map(fcfa),
            "Encaissements d'exploitation": enc[idx].map(fcfa),
            "Décaissements d'exploitation": dec[idx].map(fcfa),
            "Flux d'exploitation": expl[idx].map(lambda v: fcfa(v, True)),
            "Flux de financement": fin[idx].map(lambda v: fcfa(v, True)),
            "Flux net": net[idx].map(lambda v: fcfa(v, True)),
            "Trésorerie de clôture": close[idx].map(fcfa)}), hide_index=True, width="stretch")
        st.caption("Le financement regroupe les catégories Emprunt et Prêt ; tout le reste relève de l'exploitation.")


# ───────────────────────── Onglet 3 : Réglages ─────────────────────────
def tab_reglages(ops: pd.DataFrame, cats: list[str]):
    left, right = st.columns(2, gap="large")
    with left, st.container(border=True):
        card_title("Catégories", "category")
        st.write(", ".join(cats) if cats else "Aucune catégorie.")
        n1, n2 = st.columns([3, 1], vertical_alignment="bottom")
        new = n1.text_input("Nouvelle catégorie", placeholder="Ex. : Santé", key="new_cat")
        if n2.button("Ajouter", icon=":material/add:", width="stretch"):
            name = new.strip()
            if not name:
                st.error("Saisissez un nom de catégorie.")
            elif name.lower() in [c.lower() for c in cats]:
                st.error("Cette catégorie existe déjà.")
            else:
                save(ops, cats + [name])
                flash(f"Catégorie « {name} » ajoutée")
                st.rerun()
        r1, r2 = st.columns([3, 1], vertical_alignment="bottom")
        rem = r1.multiselect("Retirer des catégories", cats, key="rem_cat")
        if r2.button("Retirer", icon=":material/remove:", width="stretch", disabled=not rem):
            used = ops["Catégorie"].isin(rem).sum()
            save(ops, [c for c in cats if c not in rem])
            flash(f"{len(rem)} catégorie(s) retirée(s)"
                  + (f" ; {used} opération(s) conservent l'ancien nom" if used else ""))
            st.rerun()
    with right, st.container(border=True):
        card_title("Base de données", "database")
        st.metric("Opérations enregistrées", len(ops))
        st.caption(f"Fichier : {DATA_FILE}")
        if DATA_FILE.exists():
            st.download_button("Télécharger le fichier Excel", DATA_FILE.read_bytes(),
                               file_name=DATA_FILE.name, icon=":material/download:",
                               mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")

    with st.container(border=True):
        card_title("Supprimer des enregistrements", "delete")
        if ops.empty:
            st.caption("Aucun enregistrement à supprimer.")
            return
        q = st.text_input("Rechercher", placeholder="Libellé ou catégorie", key="q_del")
        view = ops.sort_values(["Date", "ID"], ascending=False)
        if q:
            mask = (view["Libellé"].str.contains(q, case=False, regex=False)
                    | view["Catégorie"].str.contains(q, case=False, regex=False))
            view = view[mask]
        tbl = pd.DataFrame({"Supprimer": False, "ID": view["ID"], "Date": view["Date"].dt.date,
                            "Nature": view["Nature"], "Catégorie": view["Catégorie"],
                            "Libellé": view["Libellé"], "Montant": view["Montant"]})
        key = f"del_{st.session_state.get('del_n', 0)}"
        edited = st.data_editor(
            tbl, hide_index=True, width="stretch", key=key, height=320,
            disabled=[c for c in tbl.columns if c != "Supprimer"],
            column_config={"Date": st.column_config.DateColumn("Date", format="DD/MM/YYYY"),
                           "Montant": st.column_config.NumberColumn("Montant (FCFA)", format="%.0f")})
        ids = edited.loc[edited["Supprimer"], "ID"].tolist()
        if st.button(f"Supprimer la sélection ({len(ids)})", type="primary",
                     icon=":material/delete:", disabled=not ids):
            save(ops[~ops["ID"].isin(ids)], cats)
            st.session_state["del_n"] = st.session_state.get("del_n", 0) + 1
            flash(f"{len(ids)} enregistrement(s) supprimé(s)")
            st.rerun()


# ───────────────────────── Application ─────────────────────────
if "flash" in st.session_state:
    st.toast(st.session_state.pop("flash"), icon=":material/check_circle:")

st.markdown(f"# :material/account_balance_wallet: {APP_NAME}")
st.caption("Vos dépenses et vos ressources, de la saisie jusqu'au bilan.")

ops, cats = load()
t_saisie, t_dash, t_reg = st.tabs([":material/add_circle: Enregistrer",
                                   ":material/dashboard: Tableau de bord",
                                   ":material/settings: Réglages"])
with t_saisie:
    ops = tab_saisie(ops, cats)
with t_dash:
    v1, v2, v3 = st.tabs([":material/monitoring: Vue d'ensemble", ":material/balance: Bilan",
                          ":material/waterfall_chart: Flux de trésorerie"])
    with v1:
        view_overview(ops)
    with v2:
        view_bilan(ops)
    with v3:
        view_flux(ops)
with t_reg:
    tab_reglages(ops, cats)
