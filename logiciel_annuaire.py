import streamlit as st
import pandas as pd
from datetime import datetime
import io

st.set_page_config(page_title="Annuaire Dynamique - France Routage", layout="wide")

st.title("📘 Annuaire Dynamique - France Routage")
st.caption("Développé par Chaymae Taj 🌸 — version DAF conforme aux règles de Sandrine")

# --------------------------------------------------
# 📂 Téléchargement des fichiers
# --------------------------------------------------
st.sidebar.header("🔹 Charger les fichiers sources")
annuaire_file = st.sidebar.file_uploader("Fichier Annuaire (.xlsx)", type=["xlsx"])
gestcom_file = st.sidebar.file_uploader("Fichier Gestcom (.xlsx)", type=["xlsx"])
jalixe_file = st.sidebar.file_uploader("Fichier Jalixe (.xlsx)", type=["xlsx"])

if annuaire_file and gestcom_file and jalixe_file:

    st.info("🔧 Nettoyage et correspondances en cours...")

    # Lecture des 3 bases
    df_annuaire = pd.read_excel(annuaire_file)
    df_gestcom = pd.read_excel(gestcom_file)
    df_jalixe = pd.read_excel(jalixe_file)

    # --------------------------------------------------
    # 🧹 Nettoyage des données
    # --------------------------------------------------
    df_annuaire["CT_Num"] = df_annuaire["CT_Num"].astype(str).str.strip()
    df_gestcom["CT_Num"] = df_gestcom["CT_Num"].astype(str).str.strip()
    df_jalixe["CptPhase"] = df_jalixe["CptPhase"].astype(str).str.strip()
    df_jalixe["LibTitre"] = df_jalixe["LibTitre"].astype(str).str.strip()

    # --------------------------------------------------
    # 🎯 Filtrage Gestcom : uniquement AR_REF = NOTE
    # --------------------------------------------------
    df_gestcom = df_gestcom[df_gestcom["AR_Ref"].astype(str).str.upper() == "NOTE"]

    # --------------------------------------------------
    # 🔗 Liaison 1 : Annuaire ↔ Gestcom sur CT_Num
    # --------------------------------------------------
    df_jointure_1 = pd.merge(
        df_annuaire,
        df_gestcom[["CT_Num", "DL_Design", "DO_Ref"]],
        on="CT_Num",
        how="left"
    )

    # --------------------------------------------------
    # 🔗 Liaison 2 : Gestcom ↔ Jalixe sur DL_Design = CptPhase
    # --------------------------------------------------
    df_final = pd.merge(
        df_jointure_1,
        df_jalixe[["CptPhase", "LibTitre"]],
        left_on="DL_Design",
        right_on="CptPhase",
        how="left"
    )

    # --------------------------------------------------
    # 🧠 Création colonne Liste_Titres_Associés
    # --------------------------------------------------
    df_final["LibTitre"] = df_final["LibTitre"].fillna("Aucun titre")
    df_final["LibTitre"] = df_final["LibTitre"].astype(str)

    df_grouped = (
        df_final.groupby("CT_Num", as_index=False)
        .agg({
            "CT_Intitule": "first",
            "CT_Contact": "first",
            "CT_Adresse": "first",
            "CT_CodePostal": "first",
            "CT_Ville": "first",
            "CT_Pays": "first",
            "CT_Telephone": "first",
            "CT_EMail": "first",
            "DO_Ref": lambda x: "; ".join(sorted(set([str(v) for v in x if pd.notna(v)]))),
            "LibTitre": lambda x: "; ".join(sorted(set([str(t) for t in x if pd.notna(t) and t != ""])))
        })
    )

    # --------------------------------------------------
    # 🕒 Ajout colonne de mise à jour
    # --------------------------------------------------
    now = datetime.now().strftime("%d/%m/%Y %H:%M")
    df_grouped["Données_mises_à_jour_le"] = now

    # --------------------------------------------------
    # 📊 Contrôle qualité (écart ≤ 1 %)
    # --------------------------------------------------
    nb_annuaire = df_annuaire["CT_Num"].nunique()
    nb_final = df_grouped["CT_Num"].nunique()
    ecart = abs(nb_annuaire - nb_final) / nb_annuaire * 100
    st.write(f"📈 Nb clients Annuaire : **{nb_annuaire}** — Nb clients Final : **{nb_final}** — Écart : {ecart:.2f}%")

    if ecart <= 1:
        st.success("✅ Contrôle OK : écart ≤ 1 %")
    else:
        st.warning("⚠️ Écart supérieur à 1 %, à vérifier.")

    # --------------------------------------------------
    # 📤 Export Excel
    # --------------------------------------------------
    output = io.BytesIO()
    with pd.ExcelWriter(output, engine="openpyxl") as writer:
        df_grouped.to_excel(writer, index=False, sheet_name="Annuaire_Dynamique")

    st.success("✅ Traitement terminé ! Données prêtes à l’export.")

    st.download_button(
        label="📦 Télécharger le fichier Excel final",
        data=output.getvalue(),
        file_name=f"Annuaire_Dynamique_{datetime.now().strftime('%Y%m%d_%H%M')}.xlsx",
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    )

    # --------------------------------------------------
    # 📋 Aperçu Streamlit
    # --------------------------------------------------
    st.dataframe(df_grouped)

else:
    st.warning("⬅️ Merci de charger les 3 fichiers (Annuaire, Gestcom, Jalixe) avant de lancer le traitement.")
