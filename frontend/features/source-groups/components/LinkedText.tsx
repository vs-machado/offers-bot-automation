import { Fragment } from "react";

type LinkedTextProps = {
  text: string;
};

export function LinkedText({ text }: LinkedTextProps) {
  return text.split(/(https?:\/\/[^\s]+)/g).map((part, index) => {
    if (!part) {
      return null;
    }

    if (part.startsWith("http://") || part.startsWith("https://")) {
      const trailingMatch = part.match(/[),.;:!?]+$/);
      const trailing = trailingMatch?.[0] ?? "";
      const url = trailing ? part.slice(0, -trailing.length) : part;

      return (
        <Fragment key={`${part}-${index}`}>
          <a
            className="break-all font-semibold text-sky-700 underline decoration-sky-300 underline-offset-2 hover:text-sky-900 dark:text-sky-300 dark:decoration-sky-500/70 dark:hover:text-sky-100"
            href={url}
            rel="noreferrer"
            target="_blank"
          >
            {url}
          </a>
          {trailing}
        </Fragment>
      );
    }

    return part.split("\n").map((line, lineIndex) => (
      <Fragment key={`${part}-${index}-${lineIndex}`}>
        {lineIndex > 0 ? <br /> : null}
        {line}
      </Fragment>
    ));
  });
}
