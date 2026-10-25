import React from "react";

export function TableRowSkeleton({ columns = 5 }: { columns?: number }) {
  return (
    <tr className="border-b border-[#1F262E] animate-pulse">
      {Array.from({ length: columns }).map((_, i) => (
        <td key={i} className="py-4 px-4">
          <div className="h-4 bg-[#171C21] rounded-md w-3/4" />
        </td>
      ))}
    </tr>
  );
}

export function CardSkeleton() {
  return (
    <div className="bg-[#111519] border border-[#1F262E] rounded-xl p-6 animate-pulse space-y-4">
      <div className="h-5 bg-[#171C21] rounded-md w-1/3" />
      <div className="h-4 bg-[#171C21]/70 rounded-md w-2/3" />
      <div className="space-y-2 pt-2">
        <div className="h-4 bg-[#171C21]/70 rounded-md" />
        <div className="h-4 bg-[#171C21]/70 rounded-md w-5/6" />
      </div>
    </div>
  );
}
