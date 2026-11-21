import { Logo } from "./components/Logo";
import { Upload } from "lucide-react";
import Link from "next/link";

export default function Home() {
  return (
    <main className="text-ink">
      <div className="mx-auto max-w-300 px-8">
        <header className="flex flex-row items-center justify-between py-6">
          <h1 className="flex items-center gap-2.5 font-display font-bold text-2xl">
            <Logo />
            StudySync
          </h1>
        </header>
        <section className="grid items-center gap-14 py-10 md:grid-cols-2">
          <div className="flex flex-col items-start gap-8">
            <h1 className="bg-brand-tint font-display font-semibold px-3 py-1.5 rounded-full text-sm text-brand-dark">
              AI-powered study workspace
            </h1>
            <h1 className="font-display font-extrabold text-6xl">
              Messy notes in. Clear study materials out
            </h1>
            <p className="font-display text-lg">
              Upload your notes, PDFs, slides and documents. StudySync turns
              them into summaries, study guides and practice quizzes, all in one
            </p>
            <div className="flex flex-row gap-10">
              <Link
                href="#upload"
                className="bg-indigo-600 font-display font-extrabold text-md text-surface px-6 py-3 rounded-xl"
              >
                Upload your notes
              </Link>
              <Link
                href="#how"
                className="bg-white border-surface-line border-2 font-display font-extrabold text-md px-6 py-3 rounded-xl"
              >
                See how it works
              </Link>
            </div>
          </div>
          <div id="upload" className="bg-white border-surface-line border-2 px-6 py-3 rounded-lg">
            <div>
              <Upload></Upload>
            </div>
          </div>
          <div></div>
        </section>
      </div>
    </main>
  );
}
