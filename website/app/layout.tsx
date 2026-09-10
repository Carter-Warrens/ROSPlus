import type { Metadata } from 'next';
import { Geist, Geist_Mono } from 'next/font/google';
import './globals.css';

const geistSans = Geist({
  variable: '--font-geist-sans',
  subsets: ['latin'],
});

const geistMono = Geist_Mono({
  variable: '--font-geist-mono',
  subsets: ['latin'],
});

export const metadata: Metadata = {
  title: {
    default: 'ROSPlus — The Performance Layer for ROS 2',
    template: '%s — ROSPlus',
  },
  description: 'A dual-mode runtime add-on for ROS 2 that gives new robotics code a high-performance path while existing nodes run unmodified.',
  applicationName: 'ROSPlus',
  authors: [{ name: 'Carter Warrens LLC', url: 'https://www.carterwarrens.com/' }],
  creator: 'Carter Warrens LLC',
  publisher: 'Carter Warrens LLC',
  category: 'Robotics developer tools',
  keywords: [
    'ROSPlus',
    'ROS 2',
    'robotics runtime',
    'ROS 2 executor',
    'Rust robotics',
    'robotics safety monitor',
    'ROS 1 migration',
    'robot fleet management',
    'robotics developer tools',
  ],
  metadataBase: new URL('https://ros-plus.com'),
  alternates: { canonical: '/' },
  manifest: '/site.webmanifest',
  robots: {
    index: true,
    follow: true,
    googleBot: {
      index: true,
      follow: true,
      'max-image-preview': 'large',
      'max-snippet': -1,
      'max-video-preview': -1,
    },
  },
  openGraph: {
    title: 'ROSPlus — The Performance Layer for ROS 2',
    description: 'Keep the ecosystem. Change the ceiling.',
    url: '/',
    siteName: 'ROSPlus',
    locale: 'en_US',
    type: 'website',
    images: [{ url: '/og.png', width: 1200, height: 630, alt: 'ROSPlus — The Performance Layer for ROS 2' }],
  },
  twitter: {
    card: 'summary_large_image',
    title: 'ROSPlus — The Performance Layer for ROS 2',
    description: 'A dual-mode runtime add-on for ROS 2.',
    images: ['/og.png'],
  },
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="en">
      <body
        className={`${geistSans.variable} ${geistMono.variable} antialiased`}
      >
        {children}
      </body>
    </html>
  );
}
