import React, { useState, useMemo } from 'react';
import { Upload, Download, RefreshCw, Search, X, AlertCircle, CheckCircle } from 'lucide-react';

const AnnuaireDynamique = () => {
  const [annuaireData, setAnnuaireData] = useState([]);
  const [gestcomData, setGestcomData] = useState([]);
  const [jalixeData, setJalixeData] = useState([]);
  const [loading, setLoading] = useState(false);
  const [lastUpdate, setLastUpdate] = useState(null);
  const [filters, setFilters] = useState({});
  const [diagnostics, setDiagnostics] = useState(null);

  const parseCSV = (text) => {
    const lines = text.split('\n').filter(line => line.trim());
    if (lines.length === 0) return [];
    const headers = lines[0].split(/[;,]/).map(h => h.trim().replace(/"/g, ''));
    return lines.slice(1).map(line => {
      const values = line.split(/[;,]/).map(v => v.trim().replace(/"/g, ''));
      const obj = {};
      headers.forEach((header, i) => {
        obj[header] = values[i] || '';
      });
      return obj;
    });
  };

  const handleFileUpload = async (e, type) => {
    const file = e.target.files[0];
    if (!file) return;

    setLoading(true);
    const text = await file.text();
    const data = parseCSV(text);

    if (type === 'annuaire') setAnnuaireData(data);
    if (type === 'gestcom') setGestcomData(data);
    if (type === 'jalixe') setJalixeData(data);

    setLoading(false);
  };

  const mergedData = useMemo(() => {
    if (!annuaireData.length || !gestcomData.length || !jalixeData.length) {
      return [];
    }

    setLastUpdate(new Date());

    const gestcomWithNote = gestcomData.filter(g => 
      g.DL_Design && (g.DL_Design.includes('{note}') || g.DL_Design.includes('note'))
    );

    const phaseNumbers = gestcomWithNote.map(g => {
      const match = g.DL_Design.match(/\d{8,}/);
      return match ? match[0] : null;
    }).filter(Boolean);

    const jalixePhases = jalixeData.map(j => j.CptPhase).filter(Boolean);
    const matches = phaseNumbers.filter(p => jalixePhases.includes(p));

    setDiagnostics({
      totalGestcom: gestcomData.length,
      gestcomWithNote: gestcomWithNote.length,
      phaseNumbers: phaseNumbers.length,
      jalixePhases: jalixePhases.length,
      matchesFound: matches.length
    });

    const titresByClient = {};

    gestcomWithNote.forEach(gRow => {
      const ctNum = gRow.CT_Num;
      if (!ctNum) return;

      const match = gRow.DL_Design.match(/\d{8,}/);
      if (!match) return;

      const phaseNum = match[0];
      const jalixeRow = jalixeData.find(j => j.CptPhase === phaseNum);
      
      if (jalixeRow && jalixeRow.Titre) {
        if (!titresByClient[ctNum]) {
          titresByClient[ctNum] = [];
        }
        if (!titresByClient[ctNum].includes(jalixeRow.Titre)) {
          titresByClient[ctNum].push(jalixeRow.Titre);
        }
      }
    });

    const uniqueClients = {};
    
    annuaireData.forEach(client => {
      const ctNum = client.CT_Num;
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

    return Object.values(uniqueClients);
  }, [annuaireData, gestcomData, jalixeData]);

  const filteredData = useMemo(() => {
    return mergedData.filter(row => {
      return Object.entries(filters).every(([key, value]) => {
        if (!value) return true;
        const cellValue = String(row[key] || '').toLowerCase();
        return cellValue.includes(value.toLowerCase());
      });
    });
  }, [mergedData, filters]);

  const handleFilterChange = (column, value) => {
    setFilters(prev => ({...prev, [column]: value}));
  };

  const exportToExcel = () => {
    const headers = ['Nom', 'CT_Num', 'Adresse', 'CP', 'Ville', 'Pays', 'Telephone', 'Email', 'Titres'];
    const csvContent = [
      headers.join(';'),
      ...filteredData.map(row => headers.map(h => '"' + (row[h] || '') + '"').join(';'))
    ].join('\n');

    const blob = new Blob([csvContent], { type: 'text/csv;charset=utf-8;' });
    const link = document.createElement('a');
    link.href = URL.createObjectURL(blob);
    link.download = 'annuaire_export_' + new Date().toISOString().slice(0,10) + '.csv';
    link.click();
  };

  const columns = ['Nom', 'CT_Num', 'Adresse', 'CP', 'Ville', 'Pays', 'Telephone', 'Email', 'Titres'];

  return (
    <div className="min-h-screen bg-gradient-to-br from-blue-50 to-indigo-100 p-6">
      <div className="max-w-7xl mx-auto">
        <div className="bg-white rounded-lg shadow-xl p-6 mb-6">
          <div className="flex justify-between items-center mb-6">
            <h1 className="text-3xl font-bold text-gray-800">📊 Annuaire Dynamique</h1>
            <p className="text-sm text-pink-600 font-medium">Développé par Chaymae Taj 🌸</p>
          </div>
          
          <div className="grid grid-cols-1 md:grid-cols-3 gap-4 mb-6">
            {['annuaire', 'gestcom', 'jalixe'].map(type => (
              <div key={type} className="border-2 border-dashed border-blue-300 rounded-lg p-4">
                <label className="flex flex-col items-center cursor-pointer">
                  <Upload className="w-8 h-8 text-blue-500 mb-2" />
                  <span className="text-sm font-medium">{type.toUpperCase()}.csv</span>
                  <span className="text-xs text-gray-500 mt-1">
                    {type === 'annuaire' && annuaireData.length > 0 && '✅ ' + annuaireData.length + ' clients'}
                    {type === 'gestcom' && gestcomData.length > 0 && '✅ ' + gestcomData.length + ' lignes'}
                    {type === 'jalixe' && jalixeData.length > 0 && '✅ ' + jalixeData.length + ' notes'}
                  </span>
                  <input type="file" accept=".csv" className="hidden" onChange={(e) => handleFileUpload(e, type)} />
                </label>
              </div>
            ))}
          </div>

          {diagnostics && (
            <div className="bg-blue-50 p-4 rounded mb-4">
              <h3 className="font-bold mb-2">🔍 Diagnostic</h3>
              <div className="text-sm grid grid-cols-2 gap-2">
                <div>GESTCOM total: <b>{diagnostics.totalGestcom}</b></div>
                <div>Avec note: <b className="text-green-600">{diagnostics.gestcomWithNote}</b></div>
                <div>Phases trouvées: <b>{diagnostics.phaseNumbers}</b></div>
                <div>Correspondances: <b className="text-blue-600">{diagnostics.matchesFound}</b></div>
              </div>
            </div>
          )}

          {mergedData.length > 0 && (
            <div className="flex justify-between items-center mb-4 p-3 bg-green-50 rounded">
              <span className="font-medium">{filteredData.length} clients affichés / {mergedData.length} total</span>
              <button onClick={exportToExcel} className="px-4 py-2 bg-green-600 text-white rounded hover:bg-green-700">
                <Download className="inline w-4 h-4 mr-2" />Exporter Excel
              </button>
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
                        ) : (
                          row[col]
                        )}
                      </td>
                    ))}
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
        
        <div className="text-center mt-6 text-gray-500 text-sm">
          © 2025 - Développé par Chaymae Taj 🌸
        </div>
      </div>
    </div>
  );
};

export default AnnuaireDynamique;


