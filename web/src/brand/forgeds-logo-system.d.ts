import type { ReactNode } from "react";

export declare const PALETTE: {
  anvilBlack: string;
  forgeFloor: string;
  anvilSteel: string;
  coolTongs: string;
  wornMetal: string;
  forgeEmber: string;
  heatedEdge: string;
  coolingMetal: string;
  deepForge: string;
  coolLinen: string;
  offWhite: string;
};

export declare const FONT_STACK: string;

export declare function resolveColors(
  variant?: "color" | "mono-dark" | "mono-light"
): { body: string; spark: string; text: string };

interface LogomarkProps {
  size?: number;
  variant?: "color" | "mono-dark" | "mono-light";
  className?: string;
}

interface WordmarkProps {
  fontSize?: number;
  variant?: "color" | "mono-dark" | "mono-light";
  className?: string;
}

interface LogoProps {
  size?: number;
  layout?: "horizontal" | "vertical";
  variant?: "color" | "mono-dark" | "mono-light";
  className?: string;
}

interface ProfilePicProps {
  size?: number;
  background?: string;
  variant?: "color" | "mono-dark" | "mono-light";
  className?: string;
}

interface SocialCardProps {
  variant?: "color" | "mono-dark" | "mono-light";
  className?: string;
}

interface GitHubBannerProps {
  variant?: "color" | "mono-dark" | "mono-light";
  className?: string;
}

export declare function Logomark(props?: LogomarkProps): ReactNode;
export declare function Wordmark(props?: WordmarkProps): ReactNode;
export declare function Logo(props?: LogoProps): ReactNode;
export declare function ProfilePic(props?: ProfilePicProps): ReactNode;
export declare function SocialCard(props?: SocialCardProps): ReactNode;
export declare function GitHubBanner(props?: GitHubBannerProps): ReactNode;

declare const _default: {
  Logomark: typeof Logomark;
  Wordmark: typeof Wordmark;
  Logo: typeof Logo;
  ProfilePic: typeof ProfilePic;
  SocialCard: typeof SocialCard;
  GitHubBanner: typeof GitHubBanner;
  PALETTE: typeof PALETTE;
  FONT_STACK: typeof FONT_STACK;
  resolveColors: typeof resolveColors;
};
export default _default;
