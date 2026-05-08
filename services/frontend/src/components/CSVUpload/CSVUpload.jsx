import { useState } from 'react';
import { Upload } from 'lucide-react';
import { uploadTransactionsCsv } from '../../api/transactions';
import { BANK_FORMAT_OPTIONS } from '../../lib/bankFormats';
import './CSVUpload.css';

function CSVUpload({ onUploadSuccess, setError, setSuccessMessage }) {
    const [selectedFile, setSelectedFile] = useState(null);
    const [bankFormat, setBankFormat] = useState('internal');

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
            const result = await uploadTransactionsCsv({ file: selectedFile, bankFormat });
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
            <select
                value={bankFormat}
                onChange={(e) => setBankFormat(e.target.value)}
                className="bank-format-select"
            >
                {BANK_FORMAT_OPTIONS.map((opt) => (
                    <option key={opt.value} value={opt.value}>{opt.label}</option>
                ))}
            </select>
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