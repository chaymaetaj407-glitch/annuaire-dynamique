import streamlit as st
import pandas as pd
from datetime import datetime
import io

st.set_page_config(page_title="Annuaire Dynamique - France Routage", layout="wide")
st.title("📘 Annuaire Dynamique - France Routage")
st.caption("Version finale conforme au modèle Sandrine – par Chaymae Taj 🌸")

# --- Téléversement des fichiers
st.sidebar.header("📂 Charger les fichiers sources")
annuaire_file = st.sidebar.file_uploader("Fichier Annuaire (.xlsx)", type=["xlsx"])
gestcom_file = st.sidebar.file_uploader("Fichier Gestcom (.xlsx)", type=["xlsx"])
jalixe_file = st.sidebar.file_uploader("Fichier Jalixe (.xlsx)", type=["xlsx"])

if annuaire_file and gestcom_file and jalixe_file:
    st.info("🔧 Nettoyage et correspondances en cours...")

    # --- Lecture des fichiers
    ann = pd.read_excel(annuaire_file)
    gest = pd.read_excel(gestcom_file)
    jal = pd.read_excel(jalixe_file)

    # --- Normalisation des champs clés
    ann["CT_Num"] = ann["CT_Num"].astype(str).str.strip()
    gest["CT_Num"] = gest["CT_Num"].astype(str).str.strip()
    gest["DL_Design"] = gest["DL_Design"].astype(str).str.strip().str.replace(".0", "", regex=False)
    jal["CptPhase"] = jal["CptPhase"].astype(str).str.strip().str.replace(".0", "", regex=False)
    jal["LibTitre"] = jal["LibTitre"].astype(str).str.strip()

    # --- Filtrage Gestcom (AR_REF = NOTE)
    gest = gest[gest["AR_Ref"].astype(str).str.upper() == "NOTE"]

    # --- Liaison Annuaire ↔ Gestcom
    joint1 = pd.merge(
        ann,
        gest[["CT_Num", "DL_Design", "DO_Ref"]],
        on="CT_Num",
        how="left"
    )

    # --- Liaison Gestcom ↔ Jalixe
    joint2 = pd.merge(
        joint1,
        jal[["CptPhase", "LibTitre"]],
        left_on="DL_Design",
        right_on="CptPhase",
        how="left"
    )

    # --- Nettoyage des titres
    joint2["LibTitre"] = joint2["LibTitre"].replace("", None)
    joint2["LibTitre"] = joint2["LibTitre"].where(joint2["LibTitre"].notna(), None)

    # --- Agrégation par client
    final = (
        joint2.groupby("CT_Num", as_index=False)
        .agg({
            "CT_Intitule": "first",
            "CT_Contact": "first",
            "CT_Adresse": "first",
            "CT_CodePostal": "first",
            "CT_Ville": "first",
            "CT_Pays": "first",
            "CT_Telephone": "first",
            "CT_EMail": "first",
            "DO_Ref": lambda x: "; ".join(sorted(set(v for v in x if pd.notna(v)))),
            "LibTitre": lambda x: "; ".join(sorted(set(t for t in x if pd.notna(t))))
        })
    )

    # --- Si aucun titre réel → afficher "Aucun titre"
    def clean_titres(val):
        if not val or val.strip() == "":
            return "Aucun titre"
        # si mélange (par ex. "Aucun titre; X") → on enlève "Aucun titre"
        titres = [t for t in val.split(";") if t.strip().lower() != "aucun titre"]
        return "; ".join(titres) if titres else "Aucun titre"

    final["LibTitre"] = final["LibTitre"].apply(clean_titres)

    # --- Ajout de la date/heure de mise à jour
    final["Données_mises_à_jour_le"] = datetime.now().strftime("%d/%m/%Y %H:%M")

    # --- Contrôle du nombre de clients (écart ≤ 1 %)
    nb_ann = ann["CT_Num"].nunique()
    nb_fin = final["CT_Num"].nunique()
    ecart = abs(nb_ann - nb_fin) / nb_ann * 100
    st.write(f"📊 Clients Annuaire : {nb_ann} | Résultat : {nb_fin} | Écart : {ecart:.2f}%")

    if ecart <= 1:
        st.success("✅ Contrôle OK : écart ≤ 1 %")
    else:
        st.warning("⚠️ Écart supérieur à 1 % (à vérifier)")

    # --- Export Excel
    output = io.BytesIO()
    with pd.ExcelWriter(output, engine="openpyxl") as writer:
        final.to_excel(writer, index=False, sheet_name="Annuaire_Dynamique")

    st.download_button(
        label="📦 Télécharger le fichier Excel final",
        data=output.getvalue(),
        file_name=f"Annuaire_Dynamique_{datetime.now().strftime('%Y%m%d_%H%M')}.xlsx",
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    )

    # --- Aperçu
    st.success("✅ Fichier prêt – identique au modèle, titres propres.")
    st.dataframe(final)

else:
    st.warning("⬅️ Merci de charger les 3 fichiers (Annuaire, Gestcom, Jalixe) avant de lancer le traitement.")
