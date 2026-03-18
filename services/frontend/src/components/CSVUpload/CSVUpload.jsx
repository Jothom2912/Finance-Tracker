// src/components/CSVUpload/CSVUpload.js
import React, { useState } from 'react';
import apiClient from '../../utils/apiClient';
import './CSVUpload.css';

function CSVUpload({ onUploadSuccess, setError, setSuccessMessage }) {
    const [selectedFile, setSelectedFile] = useState(null);

    const handleFileChange = (event) => {
        setSelectedFile(event.target.files[0]);
    };

    const handleUpload = async () => {
        if (!selectedFile) {
            setError('Vælg venligst en CSV-fil at uploade.');
            return;
        }

        const formData = new FormData();
        formData.append('file', selectedFile);

        setError(null);
        setSuccessMessage(null);

        try {
            // Brug apiClient.fetch - den håndterer nu FormData korrekt
            const response = await apiClient.fetch('/transactions/upload-csv/', {
                method: 'POST',
                body: formData,
            });

            if (!response.ok) {
                const errorData = await response.json();
                const errorMsg = typeof errorData.detail === 'string' 
                    ? errorData.detail 
                    : JSON.stringify(errorData.detail || errorData);
                throw new Error(errorMsg || `HTTP error! status: ${response.status}`);
            }

            const result = await response.json();
            setSuccessMessage(result.message || 'CSV-fil uploadet succesfuldt!');
            onUploadSuccess(); // Trigger opdatering af transaktionsliste og dashboard
            setSelectedFile(null); // Ryd det valgte filnavn
            document.getElementById('csvFile').value = ''; // Ryd filinputfeltet
        } catch (err) {
            console.error("Fejl ved upload af CSV:", err);
            setError(`Fejl ved upload: ${err.message}`);
        }
    };

    return (
        <div className="csv-upload-container">
            <h4>Upload CSV-fil</h4>
            <input
                type="file"
                id="csvFile"
                accept=".csv"
                onChange={handleFileChange}
                className="input-file"
            />
            {selectedFile && (
                <p>Valgt fil: {selectedFile.name}</p>
            )}
            <button className="button secondary" onClick={handleUpload} disabled={!selectedFile}>
                📤 Upload CSV
            </button>
        </div>
    );
}

export default CSVUpload;