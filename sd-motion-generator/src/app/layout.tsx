import React from 'react';
import { Inter } from "next/font/google";
import "./globals.css";
import localFont from 'next/font/local';

const ibiza = localFont({
  src: [
    {
      path: '../../public/fonts/Ibiza22-ExtraLight.ttf',
      weight: '200',
      style: 'normal',
    },
    {
      path: '../../public/fonts/Ibiza22-Light.ttf',
      weight: '300',
      style: 'normal',
    },
    {
      path: '../../public/fonts/Ibiza22.ttf',
      weight: '400',
      style: 'normal',
    },
    {
      path: '../../public/fonts/Ibiza22-SemiBold.ttf',
      weight: '600',
      style: 'normal',
    },
    {
      path: '../../public/fonts/Ibiza22-Bold.ttf',
      weight: '700',
      style: 'normal',
    },
    {
      path: '../../public/fonts/Ibiza22-ExtraBold.ttf',
      weight: '800',
      style: 'normal',
    },
  ],
  variable: '--font-ibiza',
});

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="sv" className={`${ibiza.variable}`}>
      <body>{children}</body>
    </html>
  );
} 