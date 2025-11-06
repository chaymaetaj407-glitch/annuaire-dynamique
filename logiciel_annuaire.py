import streamlit as st
import pandas as pd
from datetime import datetime
import io
from rapidfuzz import process, fuzz

st.set_page_config(page_title="Annuaire Dynamique - France Routage", layout="wide")
st.title("📘 Annuaire Dynamique - France Routage")

# ======= Fonction principale =======
@st.cache_data
def traiter_donnees(df_annuaire, df_gestcom, df_jalixe):
    try:
        st.info("🔧 Nettoyage et correspondances en cours...")

        # --- Vérif colonnes clés ---
        ct_col_annuaire = next((c for c in df_annuaire.columns if c.lower() in ['ct_num', 'num_ct']), None)
        ct_col_gestcom = next((c for c in df_gestcom.columns if c.lower() in ['ct_num', 'num_ct']), None)
        ar_ref_col = next((c for c in df_gestcom.columns if c.lower() == 'ar_ref'), None)
        dl_design_col = next((c for c in df_gestcom.columns if c.lower() == 'dl_design'), None)

        if not all([ct_col_annuaire, ct_col_gestcom, ar_ref_col, dl_design_col]):
            st.error("❌ Colonnes manquantes (CT_Num, AR_Ref ou DL_Design).")
            return None

        # --- Nettoyage des identifiants clients ---
        df_annuaire['CT_Num_Clean'] = df_annuaire[ct_col_annuaire].astype(str).str.strip().str.upper()
        df_gestcom['CT_Num_Clean'] = df_gestcom[ct_col_gestcom].astype(str).str.strip().str.upper()

        # --- Filtrer GESTCOM : AR_REF = NOTE ---
        df_gestcom = df_gestcom[df_gestcom[ar_ref_col].astype(str).str.upper().str.contains("NOTE", na=False)]

        # --- Nettoyage des phases ---
        df_gestcom['CptPhase_Clean'] = (
            df_gestcom[dl_design_col]
            .astype(str)
            .str.replace(r'[^A-Za-z0-9 ]', '', regex=True)
            .str.strip()
            .str.upper()
        )

        df_jalixe['CptPhase_Clean'] = (
            df_jalixe['CptPhase']
            .astype(str)
            .str.replace(r'[^A-Za-z0-9 ]', '', regex=True)
            .str.strip()
            .str.upper()
        )

        # --- Liaison exacte GESTCOM ↔ JALIXE ---
        df_gj = df_gestcom.merge(
            df_jalixe[['CptPhase_Clean', 'LibTitre']],
            on='CptPhase_Clean',
            how='left'
        )

        # Si aucun titre → "Aucun titre"
        df_gj['LibTitre'] = df_gj['LibTitre'].fillna("Aucun titre")

        # --- Liaison Annuaire ↔ GESTCOM ---
        df_final = df_annuaire.merge(
            df_gj[['CT_Num_Clean', 'LibTitre']],
            on='CT_Num_Clean',
            how='left'
        )

        # --- Concaténation des titres par client ---
        df_final_grouped = (
            df_final.groupby('CT_Num_Clean', as_index=False)
            .agg({
                ct_col_annuaire: 'first',
                'LibTitre': lambda x: '; '.join(sorted(set([t for t in x if t]))),
                **{
                    col: 'first'
                    for col in df_annuaire.columns
                    if col not in ['CT_Num_Clean', ct_col_annuaire]
                }
            })
        )

        # --- Colonnes finales ---
        colonnes_finales = [
            'CT_Num_Clean', ct_col_annuaire,
            'CT_Intitule' if 'CT_Intitule' in df_final_grouped.columns else None,
            'CT_Adresse' if 'CT_Adresse' in df_final_grouped.columns else None,
            'CT_CodePostal' if 'CT_CodePostal' in df_final_grouped.columns else None,
            'CT_Ville' if 'CT_Ville' in df_final_grouped.columns else None,
            'CT_Pays' if 'CT_Pays' in df_final_grouped.columns else None,
            'CT_Telephone' if 'CT_Telephone' in df_final_grouped.columns else None,
            'CT_EMail' if 'CT_EMail' in df_final_grouped.columns else None,
            'LibTitre'
        ]
        colonnes_finales = [c for c in colonnes_finales if c in df_final_grouped.columns]
        df_final_grouped = df_final_grouped[colonnes_finales]

        # --- Contrôle nombre clients distincts ---
        nb_clients_annuaire = df_annuaire['CT_Num_Clean'].nunique()
        nb_clients_final = df_final_grouped['CT_Num_Clean'].nunique()
        ecart = abs(nb_clients_annuaire - nb_clients_final) / nb_clients_annuaire * 100

        if ecart <= 1:
            st.success(f"✅ Contrôle validé : {nb_clients_final} clients générés "
                       f"(écart {ecart:.2f}% ≤ 1% par rapport à l'annuaire).")
        else:
            st.warning(f"⚠️ Écart trop élevé ({ecart:.2f}%) entre l'annuaire ({nb_clients_annuaire}) "
                       f"et le résultat ({nb_clients_final}).")

        st.caption(f"🕒 Données mises à jour le {datetime.now().strftime('%d/%m/%Y %H:%M')}")

        return df_final_grouped

    except Exception as e:
        st.error(f"❌ Erreur : {e}")
        import traceback
        st.code(traceback.format_exc())
        return None


# ======= Interface Streamlit =======
st.sidebar.header("📂 Charger vos fichiers")
file_annuaire = st.sidebar.file_uploader("1️⃣ Annuaire", type=["xlsx", "csv"])
file_gestcom = st.sidebar.file_uploader("2️⃣ GESTCOM", type=["xlsx", "csv"])
file_jalixe = st.sidebar.file_uploader("3️⃣ JALIXE", type=["xlsx", "csv"])

@st.cache_data
def lire_fichier(file_bytes, file_name):
    if file_name.endswith('.csv'):
        return pd.read_csv(io.BytesIO(file_bytes), sep=';', encoding='latin1', low_memory=False)
    return pd.read_excel(io.BytesIO(file_bytes))

if st.sidebar.button("🔄 Générer l'annuaire", type="primary"):
    if file_annuaire and file_gestcom and file_jalixe:
        with st.spinner("⏳ Traitement en cours..."):
            df_annuaire = lire_fichier(file_annuaire.read(), file_annuaire.name)
            df_gestcom = lire_fichier(file_gestcom.read(), file_gestcom.name)
            df_jalixe = lire_fichier(file_jalixe.read(), file_jalixe.name)

            df_final = traiter_donnees(df_annuaire, df_gestcom, df_jalixe)
            if df_final is not None:
                st.session_state['df_final'] = df_final
                st.success("🎉 Annuaire généré avec succès !")
                st.balloons()
    else:
        st.error("⚠️ Veuillez charger les 3 fichiers avant de lancer le traitement.")

if 'df_final' in st.session_state:
    df = st.session_state['df_final']
    st.markdown("---")
    st.subheader("📊 Résultat final : Annuaire Dynamique")
    st.dataframe(df, use_container_width=True, height=600)

    # --- Export Excel ---
    buffer = io.BytesIO()
    with pd.ExcelWriter(buffer, engine='openpyxl') as writer:
        df.to_excel(writer, index=False, sheet_name='Annuaire')

    st.download_button(
        label="📥 Exporter en Excel",
        data=buffer.getvalue(),
        file_name=f"Annuaire_Dynamique_{datetime.now().strftime('%Y%m%d_%H%M')}.xlsx",
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    )

st.sidebar.markdown("---")
st.sidebar.info("✨ Développé par Chaymae Taj 🌸 — Version validée DAF (Sandrine)")
