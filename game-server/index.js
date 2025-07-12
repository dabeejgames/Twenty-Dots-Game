const express = require('express');
const http = require('http');
const cors = require('cors');
const { Server } = require('socket.io');

const app = express();
app.use(cors());

const server = http.createServer(app);

const io = new Server(server, {
  cors: {
    origin: 'http://localhost:5173', // Vite's default port, change if needed
    methods: ['GET', 'POST']
  }
});

// Example: handle connections and events
io.on('connection', (socket) => {
  console.log(`User connected: ${socket.id}`);

  socket.on('joinRoom', (room) => {
    socket.join(room);
    // Send confirmation or broadcast to room
    socket.emit('roomJoined', room);
    // You can manage room state here
  });

  socket.on('playCard', (data) => {
    // Update game state, then emit new state to room
    io.to(data.room).emit('gameState', {/* updated state */});
  });

  socket.on('endTurn', (room) => {
    // Handle turn logic, then emit new state
    io.to(room).emit('gameState', {/* updated state */});
  });

  socket.on('disconnect', () => {
    console.log('User disconnected');
    // Handle cleanup
  });
});

server.listen(4000, () => {
  console.log('Server is running on port 4000');
});
