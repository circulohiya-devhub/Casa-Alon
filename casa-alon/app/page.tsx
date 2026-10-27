import Hero from "@/components/Hero";
import Philosophy from "@/components/Philosophy";
import WaveDivider from "@/components/WaveDivider";
import Rooms from "@/components/Rooms";
import Amenities from "@/components/Amenities";
import Gallery from "@/components/Gallery";
import Location from "@/components/Location";
import Testimonials from "@/components/Testimonials";
import CTA from "@/components/CTA";
import Footer from "@/components/Footer";
import ChatWidget from "@/components/ChatWidget";

export default function Home() {
  return (
    <main>
      <Hero />
      <Philosophy />
      <WaveDivider from="#EFE6D8" to="#FAF6EE" />
      <Rooms />
      <WaveDivider from="#FAF6EE" to="#1F3A3D" />
      <Amenities />
      <WaveDivider from="#1F3A3D" to="#EFE6D8" flip />
      <Gallery />
      <Location />
      <WaveDivider from="#FAF6EE" to="#1F3A3D" />
      <Testimonials />
      <WaveDivider from="#1F3A3D" to="#EFE6D8" flip />
      <CTA />
      <Footer />
      <ChatWidget />
    </main>
  );
}
