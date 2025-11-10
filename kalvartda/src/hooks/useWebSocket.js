import { useEffect, useRef, useState, useCallback } from 'react';
import io from 'socket.io-client';

/**
 * Custom hook for managing WebSocket connections
 * @param {string} url - WebSocket URL
 * @param {Object} options - Configuration options
 * @param {Function} options.onMessage - Callback for incoming messages
 * @param {Function} options.onError - Callback for errors
 * @param {Function} options.onConnect - Callback for successful connection
 * @param {Function} options.onDisconnect - Callback for disconnection
 * @returns {Object} - WebSocket utilities
 */
export const useWebSocket = (url, options = {}) => {
  const {
    onMessage,
    onError,
    onConnect,
    onDisconnect
  } = options;

  const socketRef = useRef(null);
  const [isConnected, setIsConnected] = useState(false);
  const [reconnectAttempts, setReconnectAttempts] = useState(0);

  useEffect(() => {
    // Initialize socket connection
    const socket = io(url, {
      transports: ['websocket'],
      reconnection: true,
      reconnectionDelay: 1000,
      reconnectionDelayMax: 5000,
      reconnectionAttempts: 5
    });

    socketRef.current = socket;

    // Connection event handlers
    socket.on('connect', () => {
      console.log('WebSocket connected');
      setIsConnected(true);
      setReconnectAttempts(0);
      if (onConnect) onConnect();
    });

    socket.on('disconnect', () => {
      console.log('WebSocket disconnected');
      setIsConnected(false);
      if (onDisconnect) onDisconnect();
    });

    socket.on('reconnect_attempt', (attempt) => {
      console.log(`Reconnection attempt ${attempt}`);
      setReconnectAttempts(attempt);
    });

    socket.on('reconnect_failed', () => {
      console.error('Failed to reconnect to server');
      if (onError) onError(new Error('Reconnection failed'));
    });

    // Message handler
    socket.on('message', (data) => {
      console.log('Received:', data);
      if (onMessage) onMessage(data);
    });

    // Error handler
    socket.on('error', (error) => {
      console.error('WebSocket error:', error);
      if (onError) onError(error);
    });

    // Cleanup on unmount
    return () => {
      if (socket) {
        socket.disconnect();
      }
    };
  }, [url, onMessage, onError, onConnect, onDisconnect]);

  // Send message function
  const sendMessage = useCallback((message) => {
    if (socketRef.current && isConnected) {
      console.log('Sending:', message);
      socketRef.current.emit('message', message);
      return true;
    } else {
      console.warn('Cannot send message: socket not connected');
      return false;
    }
  }, [isConnected]);

  return {
    sendMessage,
    isConnected,
    reconnectAttempts,
    socket: socketRef.current
  };
};

export default useWebSocket;
