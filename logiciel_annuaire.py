import streamlit as st
import pandas as pd
from datetime import datetime
import io

# ======================
# ⚙️ CONFIGURATION APP
# ======================
st.set_page_config(page_title="Annuaire Dynamique - France Routage", layout="wide")
st.title("📘 Annuaire Dynamique - France Routage")
st.caption("Version finale conforme aux règles Sandrine 🌸")

# ======================
# 📂 IMPORT DES FICHIERS
# ======================
st.sidebar.header("📁 Charger les fichiers sources")
annuaire_file = st.sidebar.file_uploader("Fichier Annuaire (.xlsx)", type=["xlsx"])
gestcom_file = st.sidebar.file_uploader("Fichier Gestcom (.xlsx)", type=["xlsx"])
jalixe_file = st.sidebar.file_uploader("Fichier Jalixe (.xlsx)", type=["xlsx"])

if annuaire_file and gestcom_file and jalixe_file:
    st.info("🔧 Lecture et préparation des données...")

    # --- Lecture
    ann = pd.read_excel(annuaire_file)
    gest = pd.read_excel(gestcom_file)
    jal = pd.read_excel(jalixe_file)

    # --- Normalisation des colonnes clés
    ann["CT_Num"] = ann["CT_Num"].astype(str).str.strip()
    gest["CT_Num"] = gest["CT_Num"].astype(str).str.strip()
    gest["DL_Design"] = gest["DL_Design"].astype(str).str.strip().str.replace(".0", "", regex=False)
    jal["CptPhase"] = jal["CptPhase"].astype(str).str.strip().str.replace(".0", "", regex=False)
    jal["LibTitre"] = jal["LibTitre"].astype(str).str.strip()

    # ======================
    # 🔗 LIAISONS ENTRE TABLES
    # ======================

    # Étape 1 : Filtrer Gestcom sur AR_REF = NOTE
    gest = gest[gest["AR_Ref"].astype(str).str.upper() == "NOTE"]

    # Étape 2 : Annuaire ↔ Gestcom (via CT_Num)
    joint1 = pd.merge(
        ann,
        gest[["CT_Num", "DL_Design", "DO_Ref"]],
        on="CT_Num",
        how="left"
    )

    # Étape 3 : Gestcom ↔ Jalixe (via DL_Design = CptPhase)
    joint2 = pd.merge(
        joint1,
        jal[["CptPhase", "LibTitre"]],
        left_on="DL_Design",
        right_on="CptPhase",
        how="left"
    )

    # ======================
    # 🧹 NETTOYAGE FINAL
    # ======================
    joint2["LibTitre"] = joint2["LibTitre"].replace("", None)

    # Étape 4 : 1 client = 1 ligne (titre unique)
    df_final = (
        joint2.sort_values(by=["CT_Num", "LibTitre"], na_position="last")
        .groupby("CT_Num", as_index=False)
        .agg({
            "CT_Intitule": "first",
            "CT_Contact": "first",
            "CT_Adresse": "first",
            "CT_CodePostal": "first",
            "CT_Ville": "first",
            "CT_Pays": "first",
            "CT_Telephone": "first",
            "CT_EMail": "first",
            "DO_Ref": "first",
            "LibTitre": lambda x: next((t for t in x if pd.notna(t)), "Aucun titre")
        })
    )

    # Ajouter la date de mise à jour
    df_final["Données_mises_à_jour_le"] = datetime.now().strftime("%d/%m/%Y %H:%M")

    # ======================
    # ✅ CONTRÔLES QUALITÉ
    # ======================
    nb_ann = ann["CT_Num"].nunique()
    nb_fin = df_final["CT_Num"].nunique()
    ecart = abs(nb_ann - nb_fin) / nb_ann * 100

    if ecart <= 1:
        st.success(f"✅ Contrôle OK : {nb_fin}/{nb_ann} clients (écart {ecart:.2f}%)")
    else:
        st.warning(f"⚠️ Écart supérieur à 1% ({ecart:.2f}%) entre Annuaire et Résultat.")

    # ======================
    # 📊 AFFICHAGE ET EXPORT
    # ======================
    st.subheader("📋 Aperçu du fichier final")
    st.dataframe(df_final, use_container_width=True)

    # Export Excel
    buffer = io.BytesIO()
    with pd.ExcelWriter(buffer, engine="openpyxl") as writer:
        df_final.to_excel(writer, index=False, sheet_name="Annuaire_Dynamique")

    st.download_button(
        label="📦 Télécharger le fichier Excel final",
        data=buffer.getvalue(),
        file_name=f"Annuaire_Dynamique_{datetime.now().strftime('%Y%m%d_%H%M')}.xlsx",
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    )

    st.success("🎉 Fichier généré avec succès : 1 client = 1 titre propre !")

else:
    st.warning("⬅️ Merci de charger les 3 fichiers : Annuaire, Gestcom, Jalixe.")
