import React from 'react';
import { ApiError } from '../../api/errors';
import './ErrorBoundary.css';

class ErrorBoundary extends React.Component {
  constructor(props) {
    super(props);
    this.state = { error: null };
  }

  static getDerivedStateFromError(error) {
    return { error };
  }

  handleReset = () => {
    this.setState({ error: null });
  };

  render() {
    const { error } = this.state;
    if (!error) return this.props.children;

    const isApi = error instanceof ApiError;

    return (
      <div className="error-boundary">
        <div className="error-boundary__card">
          <h2 className="error-boundary__title">
            {isApi ? 'Noget gik galt med serveren' : 'Uventet fejl'}
          </h2>
          <p className="error-boundary__message">{error.message}</p>
          {isApi && error.status && (
            <p className="error-boundary__status">HTTP {error.status}</p>
          )}
          <div className="error-boundary__actions">
            <button className="error-boundary__btn" onClick={this.handleReset}>
              Prøv igen
            </button>
            <button
              className="error-boundary__btn error-boundary__btn--secondary"
              onClick={() => window.location.assign('/dashboard')}
            >
              Gå til dashboard
            </button>
          </div>
        </div>
      </div>
    );
  }
}

export default ErrorBoundary;
