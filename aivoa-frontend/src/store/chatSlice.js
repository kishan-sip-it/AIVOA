import { createSlice } from "@reduxjs/toolkit";

const initialState = {
  messages: [
    {
      id: "welcome",
      role: "assistant",
      content:
        "Hi, I'm the AIVOA Copilot. Paste a complaint narrative or attach a document and I'll extract the intake fields for you. Once fields are filled, you can ask me to correct any of them — e.g. \"change batch number to XYZ-123\".",
      timestamp: new Date().toISOString(),
    },
  ],
};

const chatSlice = createSlice({
  name: "chat",
  initialState,
  reducers: {
    addMessage(state, action) {
      state.messages.push(action.payload);
    },
    clearMessages(state) {
      state.messages = [];
    },
    resetChat() {
      return initialState;
    },
  },
});

export const { addMessage, clearMessages, resetChat } = chatSlice.actions;
export default chatSlice.reducer;