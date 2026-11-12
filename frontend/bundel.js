// Ingang voor de bundel: alles wat het bewerkscherm (artikel-editor.js) van Tiptap gebruikt, onder window.KBTiptap.
export { Editor, Node, Mark, Extension, mergeAttributes } from "@tiptap/core";
export { default as StarterKit } from "@tiptap/starter-kit";
export { Table, TableRow, TableCell, TableHeader } from "@tiptap/extension-table";
export { default as Subscript } from "@tiptap/extension-subscript";
export { default as Superscript } from "@tiptap/extension-superscript";
export { Plugin, PluginKey, TextSelection, NodeSelection } from "@tiptap/pm/state";
export { Decoration, DecorationSet } from "@tiptap/pm/view";
export { Fragment } from "@tiptap/pm/model";
