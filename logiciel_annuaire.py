import React, { useState, useMemo } from 'react';
import { Upload, Download, RefreshCw } from 'lucide-react';

const AnnuaireDynamique = () => {
  const [annuaireData, setAnnuaireData] = useState([]);
  const [gestcomData, setGestcomData] = useState([]);
  const [jalixeData, setJalixeData] = useState([]);
  const [filters, setFilters] = useState({});
  const [diagnostics, setDiagnostics] = useState(null);
  const [lastUpdate, setLastUpdate] = useState(null);

  // --- LECTURE CSV ---
  const parseCSV = (text) => {
    const lines = text.split('\n').filter(line => line.trim());
    if (lines.length === 0) return [];
    const headers = lines[0].split(/[;,]/).map(h => h.trim().replace(/"/g, ''));
    return lines.slice(1).map(line => {
      const values = line.split(/[;,]/).map(v => v.trim().replace(/"/g, ''));
      const obj = {};
      headers.forEach((header, i) => obj[header] = values[i] || '');
      return obj;
    });
  };

  // --- UPLOAD ---
  const handleFileUpload = async (e, type) => {
    const file = e.target.files[0];
    if (!file) return;
    const text = await file.text();
    const data = parseCSV(text);
    if (type === 'annuaire') setAnnuaireData(data);
    if (type === 'gestcom') setGestcomData(data);
    if (type === 'jalixe') setJalixeData(data);
    setLastUpdate(new Date());
  };

  // --- FUSION DES DONNÉES SELON RÈGLES DAF ---
  const mergedData = useMemo(() => {
    if (!annuaireData.length || !gestcomData.length || !jalixeData.length) return [];

    // Filtrage GESTCOM : uniquement AR_Ref = "Note"
    const gestcomNotes = gestcomData.filter(
      g => g.AR_Ref && g.AR_Ref.toLowerCase() === 'note'
    );

    const titresByClient = {};

    gestcomNotes.forEach(gRow => {
      const ctNum = gRow.CT_Num;
      if (!ctNum) return;

      const design = gRow.DL_Design || '';
      const match = design.match(/\d{6,12}/); // extraction phase
      if (!match) return;

      const phaseNum = match[0].trim();

      const jalixeRow = jalixeData.find(
        j => j.CptPhase && j.CptPhase.toString().trim() === phaseNum
      );

      if (jalixeRow && jalixeRow.Titre) {
        if (!titresByClient[ctNum]) titresByClient[ctNum] = [];
        if (!titresByClient[ctNum].includes(jalixeRow.Titre)) {
          titresByClient[ctNum].push(jalixeRow.Titre);
        }
      }
    });

    // --- Construction tableau unique : 1 ligne = 1 client ---
    const uniqueClients = {};
    annuaireData.forEach(client => {
      const ctNum = client.CT_Num?.trim();
      if (!ctNum || uniqueClients[ctNum]) return;

      const titres = titresByClient[ctNum] || [];
      uniqueClients[ctNum] = {
        CT_Num: ctNum,
        Nom: client.CT_Intitule || '',
        Adresse: client.CT_Adresse || '',
        CP: client.CT_CodePostal || '',
        Ville: client.CT_Ville || '',
        Pays: client.CT_Pays || '',
        Telephone: client.CT_Telephone || '',
        Email: client.CT_Email || '',
        Titres: titres.length > 0 ? titres.join('; ') : 'Aucun titre'
      };
    });

    // --- Contrôle qualité ---
    const nbClients = Object.keys(uniqueClients).length;
    const nbAnnuaire = annuaireData.length;
    const ecartPct = Math.abs(nbAnnuaire - nbClients) / nbAnnuaire * 100;

    setDiagnostics({
      totalGestcom: gestcomData.length,
      gestcomNotes: gestcomNotes.length,
      phasesTrouvees: Object.values(titresByClient).flat().length,
      nbClients,
      nbAnnuaire,
      ecartPct: ecartPct.toFixed(1)
    });

    return Object.values(uniqueClients);
  }, [annuaireData, gestcomData, jalixeData]);

  // --- FILTRAGE ---
  const filteredData = useMemo(() => {
    return mergedData.filter(row =>
      Object.entries(filters).every(([key, value]) => {
        if (!value) return true;
        const cellValue = String(row[key] || '').toLowerCase();
        return cellValue.includes(value.toLowerCase());
      })
    );
  }, [mergedData, filters]);

  const handleFilterChange = (column, value) => {
    setFilters(prev => ({ ...prev, [column]: value }));
  };

  // --- EXPORT CSV ---
  const exportToExcel = () => {
    const headers = ['Nom', 'CT_Num', 'Adresse', 'CP', 'Ville', 'Pays', 'Telephone', 'Email', 'Titres'];
    const csvContent = [
      headers.join(';'),
      ...filteredData.map(row => headers.map(h => '"' + (row[h] || '') + '"').join(';'))
    ].join('\n');
    const blob = new Blob([csvContent], { type: 'text/csv;charset=utf-8;' });
    const link = document.createElement('a');
    link.href = URL.createObjectURL(blob);
    link.download = 'Annuaire_Dynamique_' + new Date().toISOString().slice(0, 10) + '.csv';
    link.click();
  };

  const columns = ['Nom', 'CT_Num', 'Adresse', 'CP', 'Ville', 'Pays', 'Telephone', 'Email', 'Titres'];

  // --- INTERFACE ---
  return (
    <div className="min-h-screen bg-gradient-to-br from-blue-50 to-indigo-100 p-6">
      <div className="max-w-7xl mx-auto">
        <div className="bg-white rounded-lg shadow-xl p-6 mb-6">
          <div className="flex justify-between items-center mb-6">
            <h1 className="text-3xl font-bold text-gray-800">📊 Annuaire Dynamique – DAF</h1>
            <p className="text-sm text-pink-600 font-medium">Développé par Chaymae Taj 🌸</p>
          </div>

          <div className="grid grid-cols-1 md:grid-cols-3 gap-4 mb-6">
            {['annuaire', 'gestcom', 'jalixe'].map(type => (
              <div key={type} className="border-2 border-dashed border-blue-300 rounded-lg p-4">
                <label className="flex flex-col items-center cursor-pointer">
                  <Upload className="w-8 h-8 text-blue-500 mb-2" />
                  <span className="text-sm font-medium">{type.toUpperCase()}.csv</span>
                  <input type="file" accept=".csv" className="hidden" onChange={(e) => handleFileUpload(e, type)} />
                </label>
              </div>
            ))}
          </div>

          {diagnostics && (
            <div className="bg-blue-50 p-4 rounded mb-4">
              <h3 className="font-bold mb-2">🔍 Diagnostic DAF</h3>
              <div className="text-sm grid grid-cols-2 gap-2">
                <div>Total Gestcom : <b>{diagnostics.totalGestcom}</b></div>
                <div>Notes Gestcom : <b className="text-blue-700">{diagnostics.gestcomNotes}</b></div>
                <div>Phases liées : <b>{diagnostics.phasesTrouvees}</b></div>
                <div>Clients uniques : <b>{diagnostics.nbClients}</b></div>
                <div>Annuaire source : <b>{diagnostics.nbAnnuaire}</b></div>
                <div>Écart : <b>{diagnostics.ecartPct}%</b></div>
              </div>
            </div>
          )}

          {mergedData.length > 0 && (
            <div className="flex justify-between items-center mb-4 p-3 bg-green-50 rounded">
              <span className="font-medium">{filteredData.length} clients affichés / {mergedData.length} total</span>
              <div className="flex gap-3 items-center">
                <button onClick={exportToExcel} className="px-4 py-2 bg-green-600 text-white rounded hover:bg-green-700">
                  <Download className="inline w-4 h-4 mr-2" />Exporter Excel
                </button>
                {lastUpdate && (
                  <span className="text-sm text-gray-500">
                    ⏰ Données mises à jour le {lastUpdate.toLocaleDateString()} à {lastUpdate.toLocaleTimeString()}
                  </span>
                )}
              </div>
            </div>
          )}
        </div>

        {mergedData.length > 0 && (
          <div className="bg-white rounded-lg shadow-xl overflow-x-auto">
            <table className="w-full">
              <thead className="bg-blue-600 text-white">
                <tr>{columns.map(col => <th key={col} className="px-4 py-3 text-left text-sm font-semibold">{col}</th>)}</tr>
                <tr className="bg-blue-50">
                  {columns.map(col => (
                    <th key={col} className="px-4 py-2">
                      <input
                        type="text"
                        placeholder="Filtrer..."
                        value={filters[col] || ''}
                        onChange={(e) => handleFilterChange(col, e.target.value)}
                        className="w-full px-2 py-1 border rounded text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
                      />
                    </th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {filteredData.map((row, idx) => (
                  <tr key={idx} className="hover:bg-blue-50 border-b">
                    {columns.map(col => (
                      <td key={col} className="px-4 py-3 text-sm">
                        {col === 'Titres' && row[col] === 'Aucun titre' ? (
                          <span className="text-red-500 italic">{row[col]}</span>
                        ) : row[col]}
                      </td>
                    ))}
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}

        <div className="text-center mt-6 text-gray-500 text-sm">
          © 2025 - Développé par Chaymae Taj 🌸 – France Routage DAF
        </div>
      </div>
    </div>
  );
};

export default AnnuaireDynamique;
