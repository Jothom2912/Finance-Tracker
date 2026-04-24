import React, { useState } from 'react';
import { Upload } from 'lucide-react';
import { uploadTransactionsCsv } from '../../api/transactions';
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

        setError(null);
        setSuccessMessage(null);

        try {
            const result = await uploadTransactionsCsv(selectedFile);
            setSuccessMessage(result.message || 'CSV-fil uploadet succesfuldt!');
            onUploadSuccess();
            setSelectedFile(null);
            document.getElementById('csvFile').value = '';
        } catch (err) {
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
                <Upload aria-hidden="true" size={16} /> Upload CSV
            </button>
        </div>
    );
}

export default CSVUpload;