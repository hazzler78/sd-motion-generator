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

export const metadata = {
  title: 'SD Motion Generator',
  description: 'Generera motioner med AI och statistik',
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="sv" className={`${ibiza.variable}`} suppressHydrationWarning>
      <head>
        <meta name="viewport" content="width=device-width, initial-scale=1" />
      </head>
      <body suppressHydrationWarning>{children}</body>
    </html>
  );
} 